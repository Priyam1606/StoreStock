let authToken = null;
let currentUserRole = null;
let currentUsername = null;

let cachedProducts = [];
let cachedStockMap = {};
let cachedCustomers = [];

function formatRupees(paise) {
  if (paise === null || paise === undefined || isNaN(paise)) return "₹0.00";
  const rs = paise / 100;
  return "₹" + rs.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function rupeesToPaise(rsVal) {
  const rs = parseFloat(rsVal);
  if (isNaN(rs)) return 0;
  return Math.round(rs * 100);
}

async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }
  if (options.body && typeof options.body === "object") {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  options.headers = headers;

  const res = await fetch(endpoint, options);
  if (res.status === 401) {
    handleLogout();
    throw new Error("Session expired or unauthorized");
  }
  return res;
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const alertEl = document.getElementById("login-alert");
  alertEl.classList.add("hidden");

  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const res = await fetch("/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      alertEl.textContent = data.detail || "Invalid login credentials";
      alertEl.classList.remove("hidden");
      return;
    }

    authToken = data.access_token;
    currentUsername = username;

    const meRes = await apiFetch("/users/me");
    if (meRes.ok) {
      const meData = await meRes.json();
      currentUserRole = meData.role;
    } else {
      currentUserRole = data.role || "staff";
    }

    setupDashboard();
  } catch (err) {
    alertEl.textContent = err.message || "Failed to sign in";
    alertEl.classList.remove("hidden");
  }
});

function handleLogout() {
  authToken = null;
  currentUserRole = null;
  currentUsername = null;
  cachedProducts = [];
  cachedStockMap = {};
  cachedCustomers = [];

  document.getElementById("login-password").value = "";
  document.getElementById("dashboard-view").classList.add("hidden");
  document.getElementById("login-view").classList.remove("hidden");
}

document.getElementById("logout-btn").addEventListener("click", handleLogout);

function setupDashboard() {
  document.getElementById("login-view").classList.add("hidden");
  document.getElementById("dashboard-view").classList.remove("hidden");

  document.getElementById("username-display").textContent = currentUsername;
  const rolePill = document.getElementById("role-pill");
  rolePill.textContent = currentUserRole.toUpperCase();
  rolePill.className = `role-pill role-${currentUserRole}`;

  const reportsNav = document.getElementById("nav-reports-tab");
  if (currentUserRole === "owner") {
    reportsNav.classList.remove("hidden");
  } else {
    reportsNav.classList.add("hidden");
  }

  switchTab("tab-products");
}

document.querySelectorAll(".nav-tab").forEach((tabBtn) => {
  tabBtn.addEventListener("click", () => {
    switchTab(tabBtn.getAttribute("data-tab"));
  });
});

function switchTab(tabId) {
  document.querySelectorAll(".nav-tab").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach((c) => c.classList.add("hidden"));

  const targetBtn = document.querySelector(`.nav-tab[data-tab="${tabId}"]`);
  if (targetBtn) targetBtn.classList.add("active");

  const targetContent = document.getElementById(tabId);
  if (targetContent) targetContent.classList.remove("hidden");

  if (tabId === "tab-products") {
    loadProducts();
  } else if (tabId === "tab-sale") {
    initSaleForm();
  } else if (tabId === "tab-customers") {
    loadCustomers();
  } else if (tabId === "tab-reports" && currentUserRole === "owner") {
    loadReports();
  }
}

async function loadProducts(query = "") {
  const tbody = document.getElementById("products-table-body");
  tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">Loading products...</td></tr>';

  try {
    const [prodRes, stockRes] = await Promise.all([
      apiFetch(`/products?limit=100&q=${encodeURIComponent(query)}`),
      apiFetch("/stock"),
    ]);

    if (!prodRes.ok) throw new Error("Failed to load products");
    cachedProducts = await prodRes.json();

    cachedStockMap = {};
    if (stockRes.ok) {
      const stockList = await stockRes.json();
      stockList.forEach((s) => {
        cachedStockMap[s.product_id] = s.current_stock;
      });
    }

    if (cachedProducts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">No products found</td></tr>';
      return;
    }

    tbody.innerHTML = "";
    cachedProducts.forEach((p) => {
      const currentStock = cachedStockMap[p.id] ?? 0;
      const isLow = currentStock <= p.reorder_level;

      const tr = document.createElement("tr");
      if (isLow) tr.classList.add("low-stock-row");

      tr.innerHTML = `
        <td><strong>${p.sku}</strong></td>
        <td>${p.name}</td>
        <td>${p.unit}</td>
        <td>${formatRupees(p.price_paise)}</td>
        <td><strong>${currentStock}</strong></td>
        <td>${p.reorder_level}</td>
        <td>
          ${isLow ? '<span class="badge badge-warning">Low Stock</span>' : '<span class="badge badge-success">In Stock</span>'}
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="color: var(--danger); text-align: center;">${err.message}</td></tr>`;
  }
}

document.getElementById("prod-search-btn").addEventListener("click", () => {
  const q = document.getElementById("prod-search").value.trim();
  loadProducts(q);
});

document.getElementById("prod-search").addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    const q = document.getElementById("prod-search").value.trim();
    loadProducts(q);
  }
});

document.getElementById("prod-refresh-btn").addEventListener("click", () => {
  loadProducts(document.getElementById("prod-search").value.trim());
});

async function initSaleForm() {
  const alertEl = document.getElementById("sale-alert");
  alertEl.className = "alert hidden";

  try {
    const [pRes, cRes, sRes] = await Promise.all([
      apiFetch("/products?limit=100"),
      apiFetch("/customers?limit=100"),
      apiFetch("/stock"),
    ]);

    if (pRes.ok) cachedProducts = await pRes.json();
    if (cRes.ok) cachedCustomers = await cRes.json();
    if (sRes.ok) {
      const stockList = await sRes.json();
      cachedStockMap = {};
      stockList.forEach((s) => (cachedStockMap[s.product_id] = s.current_stock));
    }

    const custSelect = document.getElementById("sale-customer");
    custSelect.innerHTML = '<option value="">-- Walk-in Customer (None) --</option>';
    cachedCustomers.forEach((c) => {
      if (c.active) {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = `${c.name} (${c.phone || "No phone"})`;
        custSelect.appendChild(opt);
      }
    });

    const linesContainer = document.getElementById("sale-lines-container");
    linesContainer.innerHTML = "";
    addSaleLine();
  } catch (err) {
    alertEl.textContent = err.message;
    alertEl.className = "alert alert-danger";
  }
}

function addSaleLine() {
  const container = document.getElementById("sale-lines-container");

  const row = document.createElement("div");
  row.className = "sale-line";

  const prodSelect = document.createElement("select");
  prodSelect.className = "form-control sale-line-product";
  prodSelect.required = true;
  prodSelect.innerHTML = '<option value="">-- Select Product --</option>';

  cachedProducts.forEach((p) => {
    if (p.active) {
      const stock = cachedStockMap[p.id] ?? 0;
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.dataset.price = p.price_paise;
      opt.dataset.stock = stock;
      opt.textContent = `${p.name} (${p.sku}) - ${formatRupees(p.price_paise)} [Available: ${stock}]`;
      prodSelect.appendChild(opt);
    }
  });

  const qtyInput = document.createElement("input");
  qtyInput.type = "number";
  qtyInput.className = "form-control sale-line-qty";
  qtyInput.min = "1";
  qtyInput.max = "100000";
  qtyInput.value = "1";
  qtyInput.style.maxWidth = "100px";
  qtyInput.required = true;

  const lineSubtotal = document.createElement("span");
  lineSubtotal.className = "sale-line-subtotal";
  lineSubtotal.style.minWidth = "90px";
  lineSubtotal.style.fontWeight = "600";
  lineSubtotal.textContent = "₹0.00";

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "btn btn-danger btn-sm";
  removeBtn.textContent = "✕";
  removeBtn.addEventListener("click", () => {
    if (container.children.length > 1) {
      row.remove();
      updateSaleTotal();
    }
  });

  function recalculateRow() {
    const selectedOpt = prodSelect.selectedOptions[0];
    const price = selectedOpt ? parseInt(selectedOpt.dataset.price || "0", 10) : 0;
    const qty = parseInt(qtyInput.value || "0", 10);
    const subtotal = Math.max(0, qty) * price;
    lineSubtotal.textContent = formatRupees(subtotal);
    updateSaleTotal();
  }

  prodSelect.addEventListener("change", recalculateRow);
  qtyInput.addEventListener("input", recalculateRow);

  row.appendChild(prodSelect);
  row.appendChild(qtyInput);
  row.appendChild(lineSubtotal);
  row.appendChild(removeBtn);
  container.appendChild(row);

  recalculateRow();
}

document.getElementById("add-line-btn").addEventListener("click", addSaleLine);

function updateSaleTotal() {
  let totalPaise = 0;
  document.querySelectorAll(".sale-line").forEach((row) => {
    const prodSelect = row.querySelector(".sale-line-product");
    const qtyInput = row.querySelector(".sale-line-qty");
    const selectedOpt = prodSelect ? prodSelect.selectedOptions[0] : null;
    const price = selectedOpt ? parseInt(selectedOpt.dataset.price || "0", 10) : 0;
    const qty = parseInt(qtyInput.value || "0", 10);
    if (!isNaN(qty) && qty > 0) {
      totalPaise += qty * price;
    }
  });
  document.getElementById("sale-total-display").textContent = formatRupees(totalPaise);
}

document.getElementById("sale-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const alertEl = document.getElementById("sale-alert");
  alertEl.className = "alert hidden";

  const paymentType = document.getElementById("sale-payment-type").value;
  const custVal = document.getElementById("sale-customer").value;
  const customerId = custVal ? parseInt(custVal, 10) : null;

  if (paymentType === "credit" && !customerId) {
    alertEl.textContent = "Customer is required for credit (udhaar) sales.";
    alertEl.className = "alert alert-danger";
    return;
  }

  const items = [];
  const rows = document.querySelectorAll(".sale-line");
  for (const row of rows) {
    const prodIdVal = row.querySelector(".sale-line-product").value;
    const qtyVal = row.querySelector(".sale-line-qty").value;
    if (!prodIdVal) {
      alertEl.textContent = "Please select a product for all lines.";
      alertEl.className = "alert alert-danger";
      return;
    }
    const pid = parseInt(prodIdVal, 10);
    const qty = parseInt(qtyVal, 10);
    if (isNaN(qty) || qty <= 0) {
      alertEl.textContent = "All item quantities must be greater than zero.";
      alertEl.className = "alert alert-danger";
      return;
    }
    items.push({ product_id: pid, qty });
  }

  try {
    const res = await apiFetch("/sales", {
      method: "POST",
      body: {
        payment_type: paymentType,
        customer_id: customerId,
        items,
      },
    });

    const data = await res.json();
    if (!res.ok) {
      alertEl.textContent = data.detail || `Sale failed (${res.status})`;
      alertEl.className = "alert alert-danger";
      return;
    }

    alertEl.textContent = `Sale #${data.id} recorded successfully! Total: ${formatRupees(data.total_paise)}`;
    alertEl.className = "alert alert-success";

    const sRes = await apiFetch("/stock");
    if (sRes.ok) {
      const stockList = await sRes.json();
      cachedStockMap = {};
      stockList.forEach((s) => (cachedStockMap[s.product_id] = s.current_stock));
    }

    const linesContainer = document.getElementById("sale-lines-container");
    linesContainer.innerHTML = "";
    addSaleLine();
  } catch (err) {
    alertEl.textContent = err.message || "Failed to record sale";
    alertEl.className = "alert alert-danger";
  }
});

async function loadCustomers() {
  const tbody = document.getElementById("customers-table-body");
  const paySelect = document.getElementById("pay-customer");
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Loading customers...</td></tr>';

  try {
    const res = await apiFetch("/customers?limit=100");
    if (!res.ok) throw new Error("Failed to load customers");
    cachedCustomers = await res.json();

    paySelect.innerHTML = '<option value="">-- Choose Customer --</option>';

    if (cachedCustomers.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">No customers registered</td></tr>';
      return;
    }

    tbody.innerHTML = "";

    for (const c of cachedCustomers) {
      const balRes = await apiFetch(`/customers/${c.id}/balance`);
      const balData = balRes.ok ? await balRes.json() : { balance_paise: 0 };
      const balance = balData.balance_paise;

      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.name} (Balance: ${formatRupees(balance)})`;
      paySelect.appendChild(opt);

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${c.name}</strong></td>
        <td>${c.phone || "—"}</td>
        <td>${formatRupees(c.credit_limit_paise)}</td>
        <td><span style="font-weight: 700; color: ${balance > 0 ? "var(--warning)" : balance < 0 ? "var(--success)" : "var(--text)"};">${formatRupees(balance)}</span></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="viewLedger(${c.id}, '${c.name.replace(/'/g, "\\'")}')">Ledger</button>
        </td>
      `;
      tbody.appendChild(tr);
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" style="color: var(--danger); text-align: center;">${err.message}</td></tr>`;
  }
}

window.viewLedger = async function (customerId, customerName) {
  const card = document.getElementById("ledger-card");
  const title = document.getElementById("ledger-title");
  const tbody = document.getElementById("ledger-table-body");

  title.textContent = `Ledger: ${customerName}`;
  tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">Loading ledger...</td></tr>';
  card.classList.remove("hidden");

  try {
    const res = await apiFetch(`/customers/${customerId}/ledger?limit=50`);
    if (!res.ok) throw new Error("Failed to load customer ledger");
    const entries = await res.json();

    if (entries.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No transactions found</td></tr>';
      return;
    }

    tbody.innerHTML = "";
    entries.forEach((e) => {
      const tr = document.createElement("tr");
      const dt = new Date(e.created_at).toLocaleString("en-IN");
      const isPositive = e.amount_paise > 0;
      tr.innerHTML = `
        <td>${dt}</td>
        <td><span class="badge ${isPositive ? "badge-warning" : "badge-success"}">${e.kind}</span></td>
        <td style="font-weight: 600; color: ${isPositive ? "var(--warning)" : "var(--success)"};">${isPositive ? "+" : ""}${formatRupees(e.amount_paise)}</td>
        <td>${e.note || "—"}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" style="color: var(--danger); text-align: center;">${err.message}</td></tr>`;
  }
};

document.getElementById("close-ledger-btn").addEventListener("click", () => {
  document.getElementById("ledger-card").classList.add("hidden");
});

document.getElementById("payment-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const alertEl = document.getElementById("payment-alert");
  alertEl.className = "alert hidden";

  const customerId = document.getElementById("pay-customer").value;
  const rsVal = document.getElementById("pay-amount").value;
  const note = document.getElementById("pay-note").value.trim() || undefined;

  const amountPaise = rupeesToPaise(rsVal);
  if (amountPaise <= 0) {
    alertEl.textContent = "Payment amount must be greater than zero.";
    alertEl.className = "alert alert-danger";
    return;
  }

  try {
    const res = await apiFetch(`/customers/${customerId}/payments`, {
      method: "POST",
      body: {
        amount_paise: amountPaise,
        note,
      },
    });

    const data = await res.json();
    if (!res.ok) {
      alertEl.textContent = data.detail || `Payment failed (${res.status})`;
      alertEl.className = "alert alert-danger";
      return;
    }

    alertEl.textContent = `Payment of ${formatRupees(amountPaise)} recorded successfully!`;
    alertEl.className = "alert alert-success";

    document.getElementById("pay-amount").value = "";
    document.getElementById("pay-note").value = "";
    loadCustomers();
  } catch (err) {
    alertEl.textContent = err.message || "Failed to record payment";
    alertEl.className = "alert alert-danger";
  }
});

async function loadReports() {
  if (currentUserRole !== "owner") return;

  const datePicker = document.getElementById("report-date");
  if (!datePicker.value) {
    const today = new Date().toISOString().split("T")[0];
    datePicker.value = today;
  }
  const dateStr = datePicker.value;

  try {
    const [summaryRes, topRes, credRes, valRes] = await Promise.all([
      apiFetch(`/reports/daily-summary?date=${encodeURIComponent(dateStr)}`),
      apiFetch("/reports/top-selling?limit=10"),
      apiFetch("/reports/credit-summary"),
      apiFetch("/reports/inventory-valuation"),
    ]);

    if (summaryRes.ok) {
      const s = await summaryRes.json();
      document.getElementById("stat-total-sales").textContent = formatRupees(s.total_sales_paise);
      document.getElementById("stat-cash-sales").textContent = formatRupees(s.total_cash_sales_paise);
      document.getElementById("stat-credit-sales").textContent = formatRupees(s.total_credit_sales_paise);
      document.getElementById("stat-returns").textContent = formatRupees(s.total_returns_paise);
      document.getElementById("stat-net-sales").textContent = formatRupees(s.net_sales_paise);
      document.getElementById("stat-cogs").textContent = formatRupees(s.total_cost_paise);
      document.getElementById("stat-gross-profit").textContent = formatRupees(s.gross_profit_paise);
      document.getElementById("stat-tx-count").textContent = `${s.sales_count} sales / ${s.returns_count} returns`;
    }

    const topTbody = document.getElementById("top-selling-table-body");
    if (topRes.ok) {
      const topItems = await topRes.json();
      if (topItems.length === 0) {
        topTbody.innerHTML = '<tr><td colspan="3" style="text-align: center;">No sales recorded yet</td></tr>';
      } else {
        topTbody.innerHTML = "";
        topItems.forEach((item) => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><strong>${item.name}</strong> <span style="color: var(--text-muted); font-size: 12px;">(${item.sku})</span></td>
            <td>${item.qty_sold}</td>
            <td style="font-weight: 600;">${formatRupees(item.total_revenue_paise)}</td>
          `;
          topTbody.appendChild(tr);
        });
      }
    }

    if (credRes.ok) {
      const cred = await credRes.json();
      document.getElementById("stat-credit-outstanding").textContent = formatRupees(cred.total_outstanding_paise);
    }

    if (valRes.ok) {
      const val = await valRes.json();
      document.getElementById("stat-inv-retail").textContent = formatRupees(val.total_retail_paise);
      document.getElementById("stat-inv-cost").textContent = formatRupees(val.total_cost_paise);
    }
  } catch (err) {
    console.error("Failed to load reports:", err);
  }
}

document.getElementById("fetch-report-btn").addEventListener("click", () => {
  loadReports();
});
