const marketTableBody = document.querySelector("#marketTable tbody");
const positionsTableBody = document.querySelector("#positionsTable tbody");
const ordersTableBody = document.querySelector("#ordersTable tbody");
const tradesTableBody = document.querySelector("#tradesTable tbody");
const cashBalance = document.querySelector("#cashBalance");
const orderForm = document.querySelector("#orderForm");
const orderHelp = document.querySelector("#orderHelp");
const searchInput = document.querySelector("#searchInput");
const tickBtn = document.querySelector("#tickBtn");
const resetBtn = document.querySelector("#resetBtn");
const kiteLoginBtn = document.querySelector("#kiteLoginBtn");
const kiteExchangeBtn = document.querySelector("#kiteExchangeBtn");
const kiteSyncBtn = document.querySelector("#kiteSyncBtn");
const kiteStatus = document.querySelector("#kiteStatus");
const kiteHelp = document.querySelector("#kiteHelp");
const kiteRequestToken = document.querySelector("#kiteRequestToken");
const subtitle = document.querySelector("#subtitle");
const tabs = document.querySelectorAll(".tab");
const tabPanels = document.querySelectorAll(".tab-panel");

const btSymbol = document.querySelector("#btSymbol");
const btFile = document.querySelector("#btFile");
const btLoadBtn = document.querySelector("#btLoadBtn");
const btClearBtn = document.querySelector("#btClearBtn");
const btMeta = document.querySelector("#btMeta");
const btPrevBtn = document.querySelector("#btPrevBtn");
const btNextBtn = document.querySelector("#btNextBtn");
const btIndex = document.querySelector("#btIndex");
const btCurrent = document.querySelector("#btCurrent");
const btOrderForm = document.querySelector("#btOrderForm");
const btSide = document.querySelector("#btSide");
const btQty = document.querySelector("#btQty");
const btHelp = document.querySelector("#btHelp");
const btPositionsTableBody = document.querySelector("#btPositionsTable tbody");
const btTradesTableBody = document.querySelector("#btTradesTable tbody");
const chartSymbol = document.querySelector("#chartSymbol");
const chartInterval = document.querySelector("#chartInterval");
const chartDays = document.querySelector("#chartDays");
const chartRefreshBtn = document.querySelector("#chartRefreshBtn");
const chartError = document.querySelector("#chartError");
const chartCanvas = document.querySelector("#chartCanvas");
const chartCtx = chartCanvas ? chartCanvas.getContext("2d") : null;

let chartSelection = { symbol: null, exchange: null };


const refreshAll = async () => {
  await Promise.all([
    loadMarket(),
    loadPositions(),
    loadOrders(),
    loadTrades(),
    loadState(),
    loadKiteStatus(),
    loadBacktest(),
  ]);
};

const formatMoney = (value) =>
  `₹${Number(value).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const formatTime = (ts) => {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
};

async function loadMarket() {
  const q = searchInput.value.trim();
  if (!q) {
    const res = await fetch("/api/market");
    const data = await res.json();
    renderMarketRows(data.data);
    return;
  }
  const [instRes, marketRes] = await Promise.all([
    fetch(`/api/instruments?q=${encodeURIComponent(q)}&limit=200`),
    fetch("/api/market"),
  ]);
  const inst = await instRes.json();
  const market = await marketRes.json();
  const priceMap = new Map(
    market.data.map((p) => [`${p.exchange}:${p.symbol}`, p])
  );
  const rows = inst.data.map((i) => {
    const key = `${i.exchange}:${i.tradingsymbol}`;
    const p = priceMap.get(key);
    return {
      symbol: i.tradingsymbol,
      exchange: i.exchange,
      price: p ? p.price : null,
      prev_price: p ? p.prev_price : null,
      updated_at: p ? p.updated_at : null,
    };
  });
  renderMarketRows(rows);
}

function renderMarketRows(rows) {
  const html = rows
    .map((item) => {
      const hasPrice = item.price !== null && item.price !== undefined;
      const change = hasPrice ? item.price - item.prev_price : 0;
      const pillClass = change >= 0 ? "pill up" : "pill down";
      return `
        <tr>
          <td>${item.symbol}</td>
          <td>${item.exchange}</td>
          <td>${hasPrice ? formatMoney(item.price) : "-"}</td>
          <td>${
            hasPrice
              ? `<span class="${pillClass}">${change >= 0 ? "+" : ""}${change.toFixed(
                  2
                )}</span>`
              : "-"
          }</td>
          <td>${hasPrice ? formatTime(item.updated_at) : "-"}</td>
          <td>
            <div class="action-buttons">
              <button data-action="trade" data-symbol="${item.symbol}" data-exchange="${
        item.exchange
      }">Trade</button>
              <button data-action="chart" data-symbol="${item.symbol}" data-exchange="${
        item.exchange
      }">Chart</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
  marketTableBody.innerHTML = html || "<tr><td colspan='6'>No data.</td></tr>";
  marketTableBody.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const symbol = btn.dataset.symbol;
      const exchange = btn.dataset.exchange;
      if (btn.dataset.action === "trade") {
        document.querySelector("#orderSymbol").value = symbol;
        document.querySelector("#orderExchange").value = exchange;
        document.querySelector("#orderQty").focus();
        return;
      }
      chartSelection = { symbol, exchange };
      chartSymbol.textContent = `${symbol} (${exchange})`;
      loadChart();
    });
  });
}
async function loadPositions() {
  const res = await fetch("/api/positions");
  const data = await res.json();
  if (!data.data.length) {
    positionsTableBody.innerHTML = "<tr><td colspan='6'>No positions yet.</td></tr>";
    return;
  }
  const prices = await (await fetch("/api/market")).json();
  positionsTableBody.innerHTML = data.data
    .map((pos) => {
      const market = prices.data.find(
        (p) => p.symbol === pos.symbol && p.exchange === pos.exchange
      );
      const last = market ? market.price : 0;
      const pnl = (last - pos.avg_price) * pos.qty;
      return `
        <tr>
          <td>${pos.symbol}</td>
          <td>${pos.exchange}</td>
          <td>${pos.qty}</td>
          <td>${formatMoney(pos.avg_price)}</td>
          <td>${formatMoney(last)}</td>
          <td>${pnl >= 0 ? "+" : ""}${formatMoney(pnl)}</td>
        </tr>
      `;
    })
    .join("");
}

async function loadOrders() {
  const res = await fetch("/api/orders");
  const data = await res.json();
  if (!data.data.length) {
    ordersTableBody.innerHTML = "<tr><td colspan='8'>No orders yet.</td></tr>";
    return;
  }
  ordersTableBody.innerHTML = data.data
    .slice(0, 50)
    .map(
      (o) => `
      <tr>
        <td>${formatTime(o.time)}</td>
        <td>${o.symbol}</td>
        <td>${o.side}</td>
        <td>${o.qty}</td>
        <td>${o.type}</td>
        <td>${o.limit_price ? formatMoney(o.limit_price) : "-"}</td>
        <td>${o.status}</td>
        <td>${
          o.status === "OPEN"
            ? `<button data-id="${o.id}">Cancel</button>`
            : "-"
        }</td>
      </tr>
    `
    )
    .join("");
  ordersTableBody.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/orders/${btn.dataset.id}/cancel`, { method: "POST" });
      await refreshAll();
    });
  });
}

async function loadTrades() {
  const res = await fetch("/api/trades");
  const data = await res.json();
  if (!data.data.length) {
    tradesTableBody.innerHTML = "<tr><td colspan='6'>No trades yet.</td></tr>";
    return;
  }
  tradesTableBody.innerHTML = data.data
    .slice(0, 50)
    .map(
      (t) => `
      <tr>
        <td>${formatTime(t.time)}</td>
        <td>${t.symbol}</td>
        <td>${t.side}</td>
        <td>${t.qty}</td>
        <td>${formatMoney(t.price)}</td>
        <td>${t.exchange}</td>
      </tr>
    `
    )
    .join("");
}

async function loadState() {
  const res = await fetch("/api/state");
  const data = await res.json();
  cashBalance.textContent = formatMoney(data.cash);
}

async function loadKiteStatus() {
  const res = await fetch("/api/kite/status");
  const data = await res.json();
  if (!data.configured) {
    kiteStatus.textContent = "Kite API key/secret not configured.";
    subtitle.textContent = "Local only • Delayed simulated prices (15 min)";
    return;
  }
  if (data.connected) {
    kiteStatus.textContent = "Kite connected. Live LTP is active.";
    subtitle.textContent = "Local only • Live LTP from Kite";
  } else {
    kiteStatus.textContent = "Kite configured. Not connected yet.";
    subtitle.textContent = "Local only • Delayed simulated prices (15 min)";
  }
}

orderForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    symbol: document.querySelector("#orderSymbol").value.trim().toUpperCase(),
    exchange: document.querySelector("#orderExchange").value,
    side: document.querySelector("#orderSide").value,
    qty: Number(document.querySelector("#orderQty").value),
    type: document.querySelector("#orderType").value,
    limit_price: null,
  };
  const limitRaw = document.querySelector("#orderLimit").value;
  payload.limit_price = limitRaw ? Number(limitRaw) : null;

  const res = await fetch("/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    orderHelp.textContent = err.detail || "Order rejected.";
    return;
  }
  orderHelp.textContent = "";
  orderForm.reset();
  await refreshAll();
});

searchInput.addEventListener("input", loadMarket);

tickBtn.addEventListener("click", async () => {
  await fetch("/api/tick", { method: "POST" });
  await refreshAll();
});

resetBtn.addEventListener("click", async () => {
  const ok = confirm("Reset all paper trading data?");
  if (!ok) return;
  await fetch("/api/reset", { method: "POST" });
  await refreshAll();
});

kiteLoginBtn.addEventListener("click", async () => {
  const res = await fetch("/api/kite/login-url");
  if (!res.ok) {
    const err = await res.json();
    kiteHelp.textContent = err.detail || "Unable to get login URL.";
    return;
  }
  const data = await res.json();
  kiteHelp.textContent = "Open the login URL in a new tab to authorize.";
  window.open(data.login_url, "_blank", "noopener");
});

kiteExchangeBtn.addEventListener("click", async () => {
  const token = kiteRequestToken.value.trim();
  if (!token) {
    kiteHelp.textContent = "Paste the request_token from the callback URL.";
    return;
  }
  const res = await fetch("/api/kite/exchange-token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_token: token }),
  });
  if (!res.ok) {
    const err = await res.json();
    kiteHelp.textContent = err.detail || "Token exchange failed.";
    return;
  }
  kiteHelp.textContent = "Kite connected.";
  await refreshAll();
});

kiteSyncBtn.addEventListener("click", async () => {
  const res = await fetch("/api/kite/instruments/sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ exchanges: ["NSE", "BSE", "NFO"] }),
  });
  if (!res.ok) {
    const err = await res.json();
    kiteHelp.textContent = err.detail || "Instrument sync failed.";
    return;
  }
  const data = await res.json();
  kiteHelp.textContent = `Instrument sync complete. ${data.count} rows.`;
  await loadMarket();
});

refreshAll();
setInterval(refreshAll, 5000);

chartRefreshBtn.addEventListener("click", loadChart);
chartInterval.addEventListener("change", loadChart);
chartDays.addEventListener("change", loadChart);

async function loadChart() {
  if (!chartSelection.symbol || !chartSelection.exchange) {
    chartError.textContent = "Select a symbol from the Market table.";
    return;
  }
  const interval = chartInterval.value;
  const days = chartDays.value;
  chartError.textContent = "";
  const res = await fetch(
    `/api/kite/candles?symbol=${encodeURIComponent(
      chartSelection.symbol
    )}&exchange=${encodeURIComponent(chartSelection.exchange)}&interval=${encodeURIComponent(
      interval
    )}&days=${encodeURIComponent(days)}`
  );
  if (!res.ok) {
    const err = await res.json();
    chartError.textContent = err.detail || "Failed to load chart.";
    drawEmptyChart();
    return;
  }
  const data = await res.json();
  drawCandles(data.data || []);
}

function drawEmptyChart() {
  if (!chartCtx) return;
  chartCtx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
  chartCtx.fillStyle = "#6f6a63";
  chartCtx.fillText("No data", 10, 20);
}

function drawCandles(candles) {
  if (!chartCtx) return;
  chartCtx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
  if (!candles.length) {
    drawEmptyChart();
    return;
  }
  const w = chartCanvas.width;
  const h = chartCanvas.height;
  const pad = 20;
  const highs = candles.map((c) => c.high);
  const lows = candles.map((c) => c.low);
  const max = Math.max(...highs);
  const min = Math.min(...lows);
  const range = max - min || 1;
  const candleWidth = Math.max(3, Math.floor((w - pad * 2) / candles.length));
  candles.forEach((c, i) => {
    const x = pad + i * candleWidth + candleWidth / 2;
    const yHigh = pad + ((max - c.high) / range) * (h - pad * 2);
    const yLow = pad + ((max - c.low) / range) * (h - pad * 2);
    const yOpen = pad + ((max - c.open) / range) * (h - pad * 2);
    const yClose = pad + ((max - c.close) / range) * (h - pad * 2);
    const up = c.close >= c.open;
    chartCtx.strokeStyle = up ? "#0b7d45" : "#a1001a";
    chartCtx.fillStyle = up ? "#0b7d45" : "#a1001a";
    chartCtx.beginPath();
    chartCtx.moveTo(x, yHigh);
    chartCtx.lineTo(x, yLow);
    chartCtx.stroke();
    const bodyTop = Math.min(yOpen, yClose);
    const bodyBottom = Math.max(yOpen, yClose);
    const bodyHeight = Math.max(1, bodyBottom - bodyTop);
    chartCtx.fillRect(
      x - candleWidth / 4,
      bodyTop,
      candleWidth / 2,
      bodyHeight
    );
  });
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.remove("active"));
    tabPanels.forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.querySelector(`#${tab.dataset.tab}`).classList.add("active");
  });
});

btLoadBtn.addEventListener("click", async () => {
  const file = btFile.files[0];
  if (!file) {
    btHelp.textContent = "Choose a CSV file first.";
    return;
  }
  const text = await file.text();
  const symbol = btSymbol.value.trim().toUpperCase() || "BACKTEST";
  const res = await fetch("/api/backtest/load", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, csv_text: text }),
  });
  if (!res.ok) {
    const err = await res.json();
    btHelp.textContent = err.detail || "Failed to load CSV.";
    return;
  }
  const data = await res.json();
  btHelp.textContent = `Loaded ${data.count} bars.`;
  await loadBacktest();
});

btClearBtn.addEventListener("click", () => {
  const ok = confirm("Clear backtest data?");
  if (!ok) return;
  fetch("/api/backtest/reset", { method: "POST" }).then(loadBacktest);
});

btPrevBtn.addEventListener("click", () => {
  fetch("/api/backtest/step", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ delta: -1 }),
  }).then(loadBacktest);
});

btNextBtn.addEventListener("click", () => {
  fetch("/api/backtest/step", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ delta: 1 }),
  }).then(loadBacktest);
});

btIndex.addEventListener("change", () => {
  const idx = Number(btIndex.value);
  if (!Number.isNaN(idx)) {
    fetch("/api/backtest/step", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: idx }),
    }).then(loadBacktest);
  }
});

btOrderForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const side = btSide.value;
  const qty = Number(btQty.value);
  if (!qty || qty <= 0) {
    btHelp.textContent = "Invalid quantity.";
    return;
  }
  fetch("/api/backtest/trade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ side, qty }),
  })
    .then(async (res) => {
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Trade failed.");
      }
    })
    .then(() => loadBacktest())
    .catch((err) => {
      btHelp.textContent = err.message;
    });
});

async function loadBacktest() {
  const [stateRes, tradesRes] = await Promise.all([
    fetch("/api/backtest/state"),
    fetch("/api/backtest/trades"),
  ]);
  const state = await stateRes.json();
  const trades = await tradesRes.json();
  btSymbol.value = state.symbol || "";
  btIndex.value = state.index || 0;
  if (!state.total) {
    btMeta.textContent = "No backtest data loaded.";
    btCurrent.textContent = "";
    btPositionsTableBody.innerHTML =
      "<tr><td colspan='5'>No positions yet.</td></tr>";
    btTradesTableBody.innerHTML =
      "<tr><td colspan='4'>No trades yet.</td></tr>";
    return;
  }
  btMeta.textContent = `Bars: ${state.total} • Cash: ${formatMoney(state.cash)}`;
  btCurrent.textContent = `Index ${state.index} • ${new Date(
    state.current.ts * 1000
  ).toLocaleString("en-IN")} • Price ${formatMoney(state.current.price)}`;
  const pnl = (state.current.price - state.pos_avg) * state.pos_qty;
  btPositionsTableBody.innerHTML = `
    <tr>
      <td>${state.symbol}</td>
      <td>${state.pos_qty}</td>
      <td>${formatMoney(state.pos_avg)}</td>
      <td>${formatMoney(state.current.price)}</td>
      <td>${pnl >= 0 ? "+" : ""}${formatMoney(pnl)}</td>
    </tr>
  `;
  const rows = trades.data || [];
  if (!rows.length) {
    btTradesTableBody.innerHTML =
      "<tr><td colspan='4'>No trades yet.</td></tr>";
  } else {
    btTradesTableBody.innerHTML = rows
      .slice(0, 100)
      .map(
        (t) => `
      <tr>
        <td>${new Date(t.ts * 1000).toLocaleString("en-IN")}</td>
        <td>${t.side}</td>
        <td>${t.qty}</td>
        <td>${formatMoney(t.price)}</td>
      </tr>
    `
      )
      .join("");
  }
}

loadBacktest();
