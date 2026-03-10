(function () {
  const root = document.getElementById("finance-demo")
  const seedNode = document.getElementById("finance-demo-seed")
  if (!root || !seedNode) {
    return
  }

  const endpoint = root.dataset.endpoint
  const controls = {
    liquidation_days: root.querySelector('input[name="liquidation_days"]'),
    num_trades: root.querySelector('input[name="num_trades"]'),
    risk_exponent: root.querySelector('input[name="risk_exponent"]'),
  }
  const outputs = {
    liquidation_days: root.querySelector('[data-output="liquidation_days"]'),
    num_trades: root.querySelector('[data-output="num_trades"]'),
    risk_aversion: root.querySelector('[data-output="risk_aversion"]'),
  }
  const metricNodes = Object.fromEntries(
    Array.from(document.querySelectorAll("[data-metric]")).map((node) => [node.dataset.metric, node])
  )
  const storyHeadline = document.querySelector("[data-story-headline]")
  const storyBody = document.querySelector("[data-story-body]")
  const tradeChart = document.querySelector('[data-chart="trade-list"]')
  const remainingChart = document.querySelector('[data-chart="remaining"]')
  const frontierChart = document.querySelector('[data-chart="frontier"]')
  const frontierCaption = document.querySelector('[data-chart-caption="frontier"]')
  const presetButtons = Array.from(root.querySelectorAll("[data-preset]"))
  const seedPayload = JSON.parse(seedNode.textContent)
  const integerFormatter = new Intl.NumberFormat("en-US")
  const moneyFormatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  })

  function formatMetric(name, value) {
    if (name === "expected_shortfall" || name === "std_dev" || name === "utility") {
      return moneyFormatter.format(value)
    }
    if (name === "first_trade_fraction") {
      return `${(value * 100).toFixed(1)}%`
    }
    if (name === "average_trade_size") {
      return `${integerFormatter.format(Math.round(value))} sh`
    }
    if (name === "half_life") {
      return value ? `${value.toFixed(1)} steps` : "n/a"
    }
    return String(value)
  }

  function syncOutputs() {
    outputs.liquidation_days.textContent = `${controls.liquidation_days.value} days`
    outputs.num_trades.textContent = `${controls.num_trades.value} trades`
    outputs.risk_aversion.textContent = (10 ** Number(controls.risk_exponent.value)).toExponential(2)
  }

  function readParams() {
    return {
      liquidation_days: Number(controls.liquidation_days.value),
      num_trades: Number(controls.num_trades.value),
      risk_aversion: 10 ** Number(controls.risk_exponent.value),
    }
  }

  function toPoints(values, width, height, padding) {
    const maxValue = Math.max(...values, 1)
    const minValue = Math.min(...values, 0)
    const span = maxValue - minValue || 1
    return values
      .map((value, index) => {
        const x = padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2)
        const y = height - padding - ((value - minValue) / span) * (height - padding * 2)
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(" ")
  }

  function renderBarChart(container, values) {
    const width = 680
    const height = 260
    const padding = 28
    const maxValue = Math.max(...values, 1)
    const barWidth = (width - padding * 2) / values.length
    const bars = values
      .map((value, index) => {
        const scaledHeight = (value / maxValue) * (height - padding * 2)
        const x = padding + index * barWidth
        const y = height - padding - scaledHeight
        const barW = Math.max(barWidth - 1, 1)
        return `<rect class="chart-bar" x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barW.toFixed(2)}" height="${scaledHeight.toFixed(2)}" rx="2"></rect>`
      })
      .join("")
    container.innerHTML = `
      <svg class="svg-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Trade schedule bar chart">
        <line class="chart-axis" x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}"></line>
        <line class="chart-axis" x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}"></line>
        ${bars}
      </svg>
      <div class="chart-meta">
        <span>Trade 1</span>
        <span>Trade ${values.length}</span>
      </div>
    `
  }

  function renderLineChart(container, values, startingShares) {
    const width = 680
    const height = 260
    const padding = 28
    const pathValues = [startingShares, ...values]
    container.innerHTML = `
      <svg class="svg-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Inventory remaining line chart">
        <line class="chart-axis" x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}"></line>
        <line class="chart-axis" x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}"></line>
        <polyline class="chart-line" points="${toPoints(pathValues, width, height, padding)}"></polyline>
      </svg>
      <div class="chart-meta">
        <span>${integerFormatter.format(startingShares)} shares at start</span>
        <span>${integerFormatter.format(values[values.length - 1])} shares left</span>
      </div>
    `
  }

  function renderFrontier(container, frontier, riskAversion) {
    const width = 680
    const height = 260
    const padding = 28
    const xValues = frontier.map((point) => point.std_dev)
    const yValues = frontier.map((point) => point.expected_shortfall)
    const xMin = Math.min(...xValues)
    const xMax = Math.max(...xValues)
    const yMin = Math.min(...yValues)
    const yMax = Math.max(...yValues)
    const xSpan = xMax - xMin || 1
    const ySpan = yMax - yMin || 1
    const highlight = frontier.reduce((best, point) => {
      const bestGap = Math.abs(Math.log10(best.risk_aversion) - Math.log10(riskAversion))
      const gap = Math.abs(Math.log10(point.risk_aversion) - Math.log10(riskAversion))
      return gap < bestGap ? point : best
    }, frontier[0])

    const points = frontier
      .map((point) => {
        const x = padding + ((point.std_dev - xMin) / xSpan) * (width - padding * 2)
        const y = height - padding - ((point.expected_shortfall - yMin) / ySpan) * (height - padding * 2)
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(" ")

    const highlightX = padding + ((highlight.std_dev - xMin) / xSpan) * (width - padding * 2)
    const highlightY = height - padding - ((highlight.expected_shortfall - yMin) / ySpan) * (height - padding * 2)

    container.innerHTML = `
      <svg class="svg-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Efficient frontier chart">
        <line class="chart-axis" x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}"></line>
        <line class="chart-axis" x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}"></line>
        <polyline class="chart-line chart-line-alt" points="${points}"></polyline>
        <circle class="chart-point" cx="${highlightX.toFixed(1)}" cy="${highlightY.toFixed(1)}" r="6"></circle>
      </svg>
      <div class="chart-meta">
        <span>Lower left means lower cost and lower risk</span>
        <span>Current setting: ${riskAversion.toExponential(2)}</span>
      </div>
    `

    if (frontierCaption) {
      frontierCaption.textContent = `Current point: about ${moneyFormatter.format(highlight.expected_shortfall)} shortfall at ${moneyFormatter.format(highlight.std_dev)} risk.`
    }
  }

  function render(payload) {
    storyHeadline.textContent = payload.story.headline
    storyBody.textContent = payload.story.body

    Object.entries(payload.metrics).forEach(([name, value]) => {
      if (metricNodes[name]) {
        metricNodes[name].textContent = formatMetric(name, value)
      }
    })

    renderBarChart(tradeChart, payload.series.trade_list)
    renderLineChart(remainingChart, payload.series.remaining, payload.metrics.shares_total)
    renderFrontier(frontierChart, payload.series.frontier, payload.controls.risk_aversion)
  }

  async function refresh() {
    syncOutputs()
    const params = readParams()
    const search = new URLSearchParams({
      liquidation_days: String(params.liquidation_days),
      num_trades: String(params.num_trades),
      risk_aversion: params.risk_aversion.toExponential(6),
    })
    try {
      const response = await fetch(`${endpoint}?${search.toString()}`, {
        headers: { Accept: "application/json" },
      })
      if (!response.ok) {
        return
      }
      render(await response.json())
    } catch (error) {
      console.error("finance demo refresh failed", error)
    }
  }

  let refreshTimer = null
  function scheduleRefresh() {
    syncOutputs()
    window.clearTimeout(refreshTimer)
    refreshTimer = window.setTimeout(refresh, 140)
  }

  Object.values(controls).forEach((input) => {
    input.addEventListener("input", scheduleRefresh)
    input.addEventListener("change", refresh)
  })

  presetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const preset = JSON.parse(button.dataset.preset)
      controls.liquidation_days.value = String(preset.liquidation_days)
      controls.num_trades.value = String(preset.num_trades)
      controls.risk_exponent.value = Math.log10(preset.risk_aversion).toFixed(2)
      refresh()
    })
  })

  syncOutputs()
  render(seedPayload)
})()
