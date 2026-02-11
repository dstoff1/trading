from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, date, timedelta
import threading
import time

app = Flask(__name__)
CORS(app)  # allow requests from localhost:5173 (Vite dashboard)

latest_data = {
    "price": 0,
    "high": 0,
    "low": 0,
    "volume": 0,
    "timestamp": None,
    "bars": [],  # 30-minute bars for the main chart
}


def fetch_tsla():
    """Fetch TSLA from yfinance and update latest_data with 30-minute bars."""
    try:
        tsla = yf.Ticker("TSLA")
        # today's 30-minute bars (TPO-style; profile/tails still use 5m)
        intraday = tsla.history(period="1d", interval="30m")
        if intraday.empty or len(intraday) == 0:
            return

        # build bar list for the chart
        bars = []
        for ts, row in intraday.iterrows():
            bars.append(
                {
                    "time": ts.isoformat(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                }
            )

        last = intraday.iloc[-1]
        session_volume = int(intraday["Volume"].sum())  # total volume today
        latest_data.update(
            {
                "price": float(last["Close"]),
                "high": float(last["High"]),
                "low": float(last["Low"]),
                "volume": session_volume,
                "timestamp": datetime.now().isoformat(),
                "bars": bars,
            }
        )
    except Exception as e:
        print(f"yfinance error: {e}", flush=True)


def update_tsla():
    while True:
        fetch_tsla()
        time.sleep(60)  # update every minute


def _tail_confidence(
    volume_at_price, total_session_volume, distance_from_poc, session_range
):
    """Steidlmayer-style: low participation at extreme + far from POC = high confidence."""
    if total_session_volume <= 0 or session_range <= 0:
        return 0.0
    participation_ratio = volume_at_price / total_session_volume
    distance_score = min(1.0, abs(distance_from_poc) / session_range)
    confidence = (1.0 - participation_ratio) * 0.6 + distance_score * 0.4
    return round(min(1.0, max(0.0, confidence)), 3)


def _compute_session_profile(df):
    """Compute POC, value area (70%), and Steidlmayer-style tails (single prints at extremes)."""
    if df is None or df.empty:
        return {
            "poc": None,
            "value_area_high": None,
            "value_area_low": None,
            "session_high": None,
            "session_low": None,
            "tails": [],
        }

    prices = df["Close"]
    volumes = df["Volume"]
    total_vol = float(volumes.sum())
    total_bars = len(df)
    if total_vol <= 0:
        return {
            "poc": None,
            "value_area_high": None,
            "value_area_low": None,
            "session_high": float(df["High"].max()),
            "session_low": float(df["Low"].min()),
            "tails": [],
        }

    session_high = float(df["High"].max())
    session_low = float(df["Low"].min())
    session_range = max(session_high - session_low, 1e-9)
    min_distance_poc = 0.02 * session_range  # tail must be >2% of range from POC

    # POC: price of bar with highest volume
    poc_idx = volumes.idxmax()
    poc_price = float(df.loc[poc_idx, "Close"])

    # Value area (70% of volume)
    rows = [
        {"price": float(p), "volume": float(v)}
        for p, v in zip(prices.tolist(), volumes.tolist())
    ]
    rows.sort(key=lambda r: r["volume"], reverse=True)
    target_vol = 0.7 * total_vol
    acc = 0.0
    va_prices = []
    for r in rows:
        acc += r["volume"]
        va_prices.append(r["price"])
        if acc >= target_vol:
            break
    va_high = max(va_prices) if va_prices else poc_price
    va_low = min(va_prices) if va_prices else poc_price

    # Bin by price: min 10 cents so levels are meaningful (single-print detection)
    bin_size = max(session_range / 100.0, 0.10)
    level_bars = {}
    level_volume = {}
    level_last_time = {}  # last bar timestamp at this level (for unfilled check)
    for (ts, row) in df.iterrows():
        p = float(row["Close"])
        v = float(row["Volume"])
        key = round(p / bin_size) * bin_size
        level_bars[key] = level_bars.get(key, 0) + 1
        level_volume[key] = level_volume.get(key, 0) + v
        level_last_time[key] = max(level_last_time.get(key, ts), ts)

    def _tail_unfilled_buy(key, last_ts):
        """True if no bar after last_ts traded at or below key (tail not filled)."""
        after = df.loc[df.index > last_ts]
        return after.empty or (after["Low"] > key).all()

    def _tail_unfilled_sell(key, last_ts):
        """True if no bar after last_ts traded at or above key (tail not filled)."""
        after = df.loc[df.index > last_ts]
        return after.empty or (after["High"] < key).all()

    tails = []
    seen_buy = set()
    seen_sell = set()

    # Buying tails: below VA, single print (1-2 bars), >2% from POC, unfilled only
    for key in sorted(level_bars.keys()):
        if key >= va_low:
            continue
        bar_count = level_bars[key]
        vol_at_level = level_volume[key]
        if bar_count > 2:
            continue
        distance = poc_price - key
        if distance < min_distance_poc:
            continue
        if key in seen_buy:
            continue
        last_ts = level_last_time.get(key)
        if last_ts is None or not _tail_unfilled_buy(key, last_ts):
            continue
        seen_buy.add(key)
        conf = _tail_confidence(vol_at_level, total_vol, distance, session_range)
        tails.append(
            {
                "price": round(key, 2),
                "type": "buying_tail",
                "confidence": conf,
                "tails_at_price": {"bars": bar_count, "volume": int(vol_at_level)},
            }
        )

    # Selling tails: above VA, single print, >2% from POC, unfilled only
    for key in sorted(level_bars.keys(), reverse=True):
        if key <= va_high:
            continue
        bar_count = level_bars[key]
        vol_at_level = level_volume[key]
        if bar_count > 2:
            continue
        distance = key - poc_price
        if distance < min_distance_poc:
            continue
        if key in seen_sell:
            continue
        last_ts = level_last_time.get(key)
        if last_ts is None or not _tail_unfilled_sell(key, last_ts):
            continue
        seen_sell.add(key)
        conf = _tail_confidence(vol_at_level, total_vol, distance, session_range)
        tails.append(
            {
                "price": round(key, 2),
                "type": "selling_tail",
                "confidence": conf,
                "tails_at_price": {"bars": bar_count, "volume": int(vol_at_level)},
            }
        )

    return {
        "poc": poc_price,
        "value_area_high": va_high,
        "value_area_low": va_low,
        "session_high": session_high,
        "session_low": session_low,
        "tails": tails,
    }


def _initial_balance(df, num_bars=12):
    """First hour (12 x 5m bars) high/low and range. Steidlmayer IB. Handles < 12 bars."""
    if df is None or df.empty:
        return {"high": None, "low": None, "range": None}
    n = min(num_bars, len(df))
    if n < 1:
        return {"high": None, "low": None, "range": None}
    head = df.head(n)
    ib_high = float(head["High"].max())
    ib_low = float(head["Low"].min())
    return {"high": ib_high, "low": ib_low, "range": ib_high - ib_low}


def _previous_session_profile(df, session_date):
    """Yesterday's POC, value area, and tails (simplified for context)."""
    prev = session_date - timedelta(days=1)
    mask = df.index.date == prev
    prev_df = df.loc[mask]
    if prev_df.empty or len(prev_df) < 2:
        return {
            "poc": None,
            "value_area_high": None,
            "value_area_low": None,
            "tails": [],
        }
    profile = _compute_session_profile(prev_df)
    tails_compact = [
        {"price": t["price"], "type": t["type"]}
        for t in profile["tails"]
    ]
    return {
        "poc": profile["poc"],
        "value_area_high": profile["value_area_high"],
        "value_area_low": profile["value_area_low"],
        "tails": tails_compact,
    }


def _current_tail_opportunity(all_tails, current_price, poc):
    """Nearest tail to current price + reversion target (POC). For alerts."""
    if not all_tails or poc is None or current_price is None:
        return {
            "type": None,
            "price": None,
            "distance_from_current_price": None,
            "confidence": None,
            "reversion_target": None,
        }
    best = None
    best_dist = float("inf")
    for t in all_tails:
        d = abs(current_price - t["price"])
        if d < best_dist:
            best_dist = d
            best = t
    if best is None:
        return {
            "type": None,
            "price": None,
            "distance_from_current_price": None,
            "confidence": None,
            "reversion_target": poc,
        }
    dist_from_current = round(best["price"] - current_price, 2)  # + = tail above price
    return {
        "type": best["type"],
        "price": best["price"],
        "distance_from_current_price": dist_from_current,
        "confidence": best.get("confidence"),
        "reversion_target": poc,
    }


@app.route("/api/tsla", methods=["GET"])
def get_tsla():
    """Main TSLA endpoint: quote, 30m bars, 5m profile, tails, IB, previous session."""
    try:
        tsla = yf.Ticker("TSLA")
        df = tsla.history(period="30d", interval="5m")
        current_price = latest_data.get("price") or 0
        current_tail = {"type": None, "price": None, "distance_from_poc": None}
        current_tail_opportunity = {
            "type": None,
            "price": None,
            "distance_from_current_price": None,
            "confidence": None,
            "reversion_target": None,
        }
        session_stats = {
            "poc": None,
            "value_area_high": None,
            "value_area_low": None,
            "session_high": None,
            "session_low": None,
        }
        all_tails = []
        initial_balance = {"high": None, "low": None, "range": None}
        extensions = {"above_ib": False, "below_ib": False}
        previous_session = {
            "poc": None,
            "value_area_high": None,
            "value_area_low": None,
            "tails": [],
        }

        if not df.empty and len(df) > 0:
            today = date.today()
            today_mask = df.index.date == today
            today_df = df.loc[today_mask]

            profile = _compute_session_profile(today_df)
            poc = profile["poc"]
            session_stats = {
                "poc": profile["poc"],
                "value_area_high": profile["value_area_high"],
                "value_area_low": profile["value_area_low"],
                "session_high": profile["session_high"],
                "session_low": profile["session_low"],
            }
            all_tails = profile["tails"]

            # Initial balance (first hour = 12 x 5m bars)
            ib = _initial_balance(today_df, num_bars=12)
            initial_balance = ib
            if ib["high"] is not None and ib["low"] is not None:
                extensions = {
                    "above_ib": current_price > ib["high"],
                    "below_ib": current_price < ib["low"],
                }

            # Previous session (yesterday)
            previous_session = _previous_session_profile(df, today)

            # Last tail (backward compat)
            if all_tails and poc is not None:
                last_tail = all_tails[-1]
                current_tail = {
                    "type": last_tail["type"],
                    "price": last_tail["price"],
                    "distance_from_poc": round(last_tail["price"] - poc, 2),
                }

            # Current tail opportunity (nearest tail + reversion target)
            current_tail_opportunity = _current_tail_opportunity(
                all_tails, current_price, poc
            )
            if current_tail_opportunity["reversion_target"] is None:
                current_tail_opportunity["reversion_target"] = poc

        payload = {
            **latest_data,
            "current_tail": current_tail,
            "current_tail_opportunity": current_tail_opportunity,
            "session_stats": session_stats,
            "all_tails": all_tails,
            "initial_balance": initial_balance,
            "extensions": extensions,
            "previous_session": previous_session,
        }
        return jsonify(payload)
    except Exception as e:
        print(f"/api/tsla error: {e}", flush=True)
        return jsonify(
            {
                **latest_data,
                "current_tail": {"type": None, "price": None, "distance_from_poc": None},
                "current_tail_opportunity": {
                    "type": None,
                    "price": None,
                    "distance_from_current_price": None,
                    "confidence": None,
                    "reversion_target": None,
                },
                "session_stats": {
                    "poc": None,
                    "value_area_high": None,
                    "value_area_low": None,
                    "session_high": None,
                    "session_low": None,
                },
                "all_tails": [],
                "initial_balance": {"high": None, "low": None, "range": None},
                "extensions": {"above_ib": False, "below_ib": False},
                "previous_session": {"poc": None, "value_area_high": None, "value_area_low": None, "tails": []},
            }
        )


@app.route("/")
def root():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    fetch_tsla()  # initial fetch so dashboard isn't zeros for the first minute
    thread = threading.Thread(target=update_tsla, daemon=True)
    thread.start()
    app.run(port=5000)
