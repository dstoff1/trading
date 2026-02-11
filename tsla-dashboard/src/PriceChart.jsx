import Plot from 'react-plotly.js'

function PriceChart({ data }) {
  const times = data.map((bar) => new Date(bar.time))
  const opens = data.map((bar) => bar.open)
  const highs = data.map((bar) => bar.high)
  const lows = data.map((bar) => bar.low)
  const closes = data.map((bar) => bar.close)

  return (
    <div className="chart-container">
      <Plot
        data={[
          {
            x: times,
            open: opens,
            high: highs,
            low: lows,
            close: closes,
            type: 'candlestick',
            increasing: { line: { color: '#22c55e' }, fillcolor: '#22c55e' },
            decreasing: { line: { color: '#ef4444' }, fillcolor: '#ef4444' },
            hovertemplate:
              '%{x|%H:%M}<br>O: $%{open:.2f}<br>H: $%{high:.2f}<br>L: $%{low:.2f}<br>C: $%{close:.2f}<extra>TSLA 30m</extra>',
          },
        ]}
        layout={{
          margin: { l: 40, r: 10, t: 10, b: 25 },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: '#020617',
          font: { color: '#e5e7eb' },
          xaxis: {
            showgrid: false,
            tickformat: '%H:%M',
            automargin: true,
          },
          yaxis: {
            gridcolor: '#111827',
            automargin: true,
            tickprefix: '$',
          },
          autosize: true,
        }}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler
        config={{ displayModeBar: false, responsive: true }}
      />
    </div>
  )
}

export default PriceChart

