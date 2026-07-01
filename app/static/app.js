let map;
let markersLayer;
let selectedPoint = null;
let pointsCache = [];

const els = {
  kpiSold: document.getElementById("kpiSold"),
  kpiAssets: document.getElementById("kpiAssets"),
  kpiOpen: document.getElementById("kpiOpen"),
  kpiSoon: document.getElementById("kpiSoon"),
  kpiLate: document.getElementById("kpiLate"),

  filterView: document.getElementById("filterView"),
  filterProduct: document.getElementById("filterProduct"),
  filterState: document.getElementById("filterState"),
  filterOwner: document.getElementById("filterOwner"),
  filterReview: document.getElementById("filterReview"),
  filterFieldStatus: document.getElementById("filterFieldStatus"),
  filterStage: document.getElementById("filterStage"),
  filterSearch: document.getElementById("filterSearch"),

  detailCard: document.getElementById("detailCard"),
  soldTable: document.getElementById("soldTable"),
  openTable: document.getElementById("openTable"),
  eventsList: document.getElementById("eventsList"),

  editDrawer: document.getElementById("editDrawer"),
  drawerBackdrop: document.getElementById("drawerBackdrop"),
};

function api(path, options = {}) {
  return fetch(path, options).then(async (response) => {
    if (!response.ok) {
      throw new Error(await response.text());
    }

    return response.json();
  });
}

function money(value) {
  return Number(value || 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function dateBR(value) {
  if (!value) {
    return "-";
  }

  return new Date(value + "T12:00:00").toLocaleDateString("pt-BR");
}

function badgeClass(status, type = "sold") {
  if (type === "open") {
    if (status === "Atividade atrasada") {
      return "red";
    }

    return "purple";
  }

  if (status === "Vencida") {
    return "red";
  }

  if (status === "Proxima") {
    return "yellow";
  }

  if (status === "Em dia") {
    return "green";
  }

  return "gray";
}

function markerColor(point) {
  if (point.point_type === "open") {
    if (point.status_revisao === "Atividade atrasada") {
      return "#d64545";
    }

    return "#7b4ee6";
  }

  if (point.status_revisao === "Vencida") {
    return "#d64545";
  }

  if (point.status_revisao === "Proxima") {
    return "#f3a51b";
  }

  return "#1e9b55";
}

function initials(name) {
  return (name || "")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

function createMarkerIcon(point) {
  const color = markerColor(point);

  const shape =
    point.point_type === "open"
      ? "border-radius: 7px; transform: rotate(45deg);"
      : "border-radius: 50%;";

  return L.divIcon({
    className: "",
    html: `
      <div style="
        width: 28px;
        height: 28px;
        ${shape}
        background: ${color};
        border: 4px solid white;
        box-shadow: 0 8px 18px rgba(0,0,0,.28);
      "></div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -12],
  });
}

function initMap() {
  map = L.map("map", {
    zoomControl: true,
  }).setView([-14.235, -51.9253], 4);

  const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap",
  });

  const satellite = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 18,
      attribution: "Tiles &copy; Esri",
    }
  );

  osm.addTo(map);

  L.control
    .layers(
      {
        Mapa: osm,
        Satelite: satellite,
      },
      null,
      {
        collapsed: false,
      }
    )
    .addTo(map);

  markersLayer = L.layerGroup().addTo(map);
}

async function loadOptions() {
  const options = await api("/api/options");

  options.produtos.forEach((value) => {
    els.filterProduct.insertAdjacentHTML(
      "beforeend",
      `<option value="${value}">${value}</option>`
    );
  });

  options.estados.forEach((value) => {
    els.filterState.insertAdjacentHTML(
      "beforeend",
      `<option value="${value}">${value}</option>`
    );
  });

  options.responsaveis.forEach((value) => {
    els.filterOwner.insertAdjacentHTML(
      "beforeend",
      `<option value="${value}">${value}</option>`
    );
  });

  options.situacoes.forEach((value) => {
    els.filterFieldStatus.insertAdjacentHTML(
      "beforeend",
      `<option value="${value}">${value}</option>`
    );
  });

  options.etapas.forEach((value) => {
    els.filterStage.insertAdjacentHTML(
      "beforeend",
      `<option value="${value}">${value}</option>`
    );
  });

  options.status_revisao.forEach((value) => {
    els.filterReview.insertAdjacentHTML(
      "beforeend",
      `<option value="${value}">${value}</option>`
    );
  });
}

function queryString(extra = {}) {
  const params = new URLSearchParams();

  params.set("view", extra.view || els.filterView.value);

  if (els.filterProduct.value) {
    params.set("produto", els.filterProduct.value);
  }

  if (els.filterState.value) {
    params.set("estado", els.filterState.value);
  }

  if (els.filterOwner.value) {
    params.set("responsavel", els.filterOwner.value);
  }

  if (els.filterReview.value) {
    params.set("status_revisao", els.filterReview.value);
  }

  if (els.filterFieldStatus.value) {
    params.set("situacao", els.filterFieldStatus.value);
  }

  if (els.filterStage.value) {
    params.set("etapa", els.filterStage.value);
  }

  if (els.filterSearch.value.trim()) {
    params.set("q", els.filterSearch.value.trim());
  }

  return params.toString();
}

async function loadSummary() {
  const summary = await api("/api/summary");

  els.kpiSold.textContent = summary.clientes_vendidos;
  els.kpiAssets.textContent = summary.produtos_em_campo;
  els.kpiOpen.textContent = summary.negocios_abertos;
  els.kpiSoon.textContent = summary.revisoes_proximas;
  els.kpiLate.textContent = summary.revisoes_vencidas;
}

async function loadPoints() {
  const qs = queryString();

  pointsCache = await api(`/api/map-points?${qs}`);

  renderMap();
  renderTables();

  if (selectedPoint) {
    const stillThere = pointsCache.find((point) => {
      return (
        point.point_type === selectedPoint.point_type &&
        point.asset_id === selectedPoint.asset_id &&
        point.open_deal_id === selectedPoint.open_deal_id
      );
    });

    renderDetail(stillThere || null);
  }
}

function renderMap() {
  markersLayer.clearLayers();

  const bounds = [];

  pointsCache.forEach((point) => {
    const marker = L.marker([point.latitude, point.longitude], {
      icon: createMarkerIcon(point),
    });

    const typeLabel =
      point.point_type === "sold" ? "Cliente vendido" : "Negocio aberto";

    marker.bindPopup(`
      <div class="popup-title">${point.nome_empresa}</div>
      <div class="popup-line"><strong>${typeLabel}</strong></div>
      <div class="popup-line">${point.nome_produto}</div>
      <div class="popup-line">${point.cidade}/${point.estado}</div>
      <div class="popup-line">Status: ${point.status_revisao}</div>
      <button
        class="popup-button"
        onclick="selectPoint('${point.point_type}', ${point.asset_id || "null"}, ${point.open_deal_id || "null"})"
      >
        Abrir ficha
      </button>
    `);

    marker.on("click", () =>
      selectPoint(point.point_type, point.asset_id, point.open_deal_id)
    );

    marker.addTo(markersLayer);

    bounds.push([point.latitude, point.longitude]);
  });

  if (bounds.length > 0) {
    map.fitBounds(bounds, {
      padding: [40, 40],
      maxZoom: 6,
    });
  }
}

function renderTables() {
  const sold = pointsCache.filter((point) => point.point_type === "sold");
  const open = pointsCache.filter((point) => point.point_type === "open");

  els.soldTable.innerHTML = sold
    .map((point) => {
      return `
        <tr onclick="selectPoint('sold', ${point.asset_id}, null)">
          <td><strong>${point.nome_empresa}</strong></td>
          <td>${point.nome_produto}</td>
          <td>${point.telefone}</td>
          <td>${point.cidade}/${point.estado}</td>
          <td>${point.responsavel_comercial}</td>
          <td>
            <span class="badge ${badgeClass(point.status_revisao)}">
              ${point.situacao_campo}
            </span>
          </td>
          <td>${point.posicao_correia}</td>
          <td>${dateBR(point.data_proxima_revisao)}</td>
          <td><strong>${point.dias_restantes_revisao}</strong></td>
        </tr>
      `;
    })
    .join("");

  els.openTable.innerHTML = open
    .map((point) => {
      return `
        <tr onclick="selectPoint('open', null, ${point.open_deal_id})">
          <td><strong>${point.nome_empresa}</strong></td>
          <td>${point.nome_produto}</td>
          <td>${point.telefone}</td>
          <td>${point.cidade}/${point.estado}</td>
          <td>${point.responsavel_comercial}</td>
          <td>
            <span class="badge ${badgeClass(point.status_revisao, "open")}">
              ${point.etapa_funil}
            </span>
          </td>
          <td>${point.probabilidade}%</td>
          <td>${money(point.valor)}</td>
          <td>${dateBR(point.proxima_atividade)}</td>
        </tr>
      `;
    })
    .join("");
}

function selectPoint(type, assetId, openDealId) {
  const point = pointsCache.find((item) => {
    return (
      item.point_type === type &&
      (item.asset_id === assetId || item.open_deal_id === openDealId)
    );
  });

  selectedPoint = point || null;

  renderDetail(selectedPoint);

  if (point && point.point_type === "sold") {
    loadMiniEvents(point.asset_id);
  }
}

function googleMapsUrl(point) {
  return `https://www.google.com/maps/search/?api=1&query=${point.latitude},${point.longitude}`;
}

function googleEarthUrl(point) {
  return `https://earth.google.com/web/search/${point.latitude},${point.longitude}`;
}

function renderDetail(point) {
  if (!point) {
    els.detailCard.innerHTML = `
      <div class="empty">
        <h3>Selecione um marcador</h3>
        <p>
          A ficha mostrará os dados comerciais, produto, revisão,
          correia e links externos.
        </p>
      </div>
    `;

    return;
  }

  const isSold = point.point_type === "sold";
  const badge = isSold ? point.status_revisao : point.etapa_funil;

  els.detailCard.innerHTML = `
    <div class="detail-top">
      <div class="avatar">${initials(point.nome_empresa)}</div>

      <div>
        <span class="badge ${badgeClass(point.status_revisao, point.point_type)}">
          ${badge}
        </span>

        <h3>${point.nome_empresa}</h3>
        <p>${point.cidade}/${point.estado} - ${point.endereco}</p>
      </div>
    </div>

    <div class="detail-grid">
      <div class="detail-item">
        <span>Tipo</span>
        <strong>${isSold ? "Cliente vendido" : "Negocio aberto"}</strong>
      </div>

      <div class="detail-item">
        <span>Produto</span>
        <strong>${point.nome_produto}</strong>
      </div>

      <div class="detail-item">
        <span>Telefone</span>
        <strong>${point.telefone}</strong>
      </div>

      <div class="detail-item">
        <span>Responsável empresa</span>
        <strong>${point.responsavel_empresa}</strong>
      </div>

      <div class="detail-item">
        <span>Responsável LLK</span>
        <strong>${point.responsavel_comercial}</strong>
      </div>

      <div class="detail-item">
        <span>Status negócio</span>
        <strong>${point.status_negocio}</strong>
      </div>

      <div class="detail-item">
        <span>Valor</span>
        <strong>${money(point.valor)}</strong>
      </div>

      ${
        isSold
          ? `
            <div class="detail-item">
              <span>Nº série</span>
              <strong>${point.numero_serie}</strong>
            </div>

            <div class="detail-item">
              <span>Situação campo</span>
              <strong>${point.situacao_campo}</strong>
            </div>

            <div class="detail-item">
              <span>Posição correia</span>
              <strong>${point.posicao_correia}</strong>
            </div>

            <div class="detail-item">
              <span>Manutenção</span>
              <strong>${point.responsavel_manutencao}</strong>
            </div>

            <div class="detail-item">
              <span>Próxima revisão</span>
              <strong>${dateBR(point.data_proxima_revisao)}</strong>
            </div>

            <div class="detail-item">
              <span>Dias restantes</span>
              <strong>${point.dias_restantes_revisao}</strong>
            </div>
          `
          : `
            <div class="detail-item">
              <span>Etapa funil</span>
              <strong>${point.etapa_funil}</strong>
            </div>

            <div class="detail-item">
              <span>Probabilidade</span>
              <strong>${point.probabilidade}%</strong>
            </div>

            <div class="detail-item">
              <span>Fechamento previsto</span>
              <strong>${dateBR(point.previsao_fechamento)}</strong>
            </div>

            <div class="detail-item">
              <span>Próxima atividade</span>
              <strong>${dateBR(point.proxima_atividade)}</strong>
            </div>
          `
      }
    </div>

    <div class="detail-actions">
      ${
        isSold
          ? `<button class="secondary" onclick="openDrawer(${point.asset_id})">Atualizar</button>`
          : `<button class="secondary" onclick="alert('Na versão real, isso abriria a oportunidade comercial.')">Registrar contato</button>`
      }

      <button class="primary" onclick="window.open('${googleMapsUrl(point)}', '_blank')">
        Google Maps
      </button>

      <button class="secondary" onclick="window.open('${googleEarthUrl(point)}', '_blank')">
        Google Earth
      </button>

      <button class="primary" onclick="window.open('https://app.pipedrive.com/deal/${point.pipedrive_deal_id}', '_blank')">
        Pipedrive
      </button>
    </div>

    <div class="event-mini" id="miniEvents">
      ${
        isSold
          ? "<h4>Histórico rápido</h4><p>Carregando eventos...</p>"
          : "<h4>Observação comercial</h4><p>Negócio ainda não vendido. Aparece no mapa comercial, mas não entra em revisão de campo.</p>"
      }
    </div>
  `;
}

async function loadMiniEvents(assetId) {
  const events = await api(`/api/assets/${assetId}/events`);
  const mini = document.getElementById("miniEvents");

  if (!mini) {
    return;
  }

  mini.innerHTML = `
    <h4>Histórico rápido</h4>

    ${events
      .slice(0, 4)
      .map((event) => {
        return `
          <p>
            <strong>${event.tipo_evento}</strong><br>
            ${event.descricao}<br>
            <small>${event.data_evento}</small>
          </p>
        `;
      })
      .join("")}
  `;
}

async function loadEvents() {
  const events = await api("/api/events?limit=80");

  els.eventsList.innerHTML = events
    .map((event) => {
      return `
        <article class="event-card">
          <div class="event-marker"></div>

          <div>
            <strong>${event.tipo_evento} - ${event.nome_empresa || "Sistema"}</strong>
            <p>${event.nome_produto || ""}</p>
            <p>${event.descricao}</p>
            <p>
              ${event.data_evento} -
              ${event.responsavel || "Sistema"} -
              Origem: ${event.origem}
            </p>
          </div>
        </article>
      `;
    })
    .join("");
}

function openDrawer(assetId) {
  const point = pointsCache.find((item) => item.asset_id === assetId);

  if (!point) {
    return;
  }

  document.getElementById("assetId").value = point.asset_id;
  document.getElementById("drawerSubtitle").textContent =
    `${point.nome_empresa} - ${point.nome_produto}`;

  document.getElementById("editSituation").value = point.situacao_campo;
  document.getElementById("editNextReview").value = point.data_proxima_revisao;
  document.getElementById("editMaintenanceOwner").value =
    point.responsavel_manutencao || "";

  document.getElementById("editObservation").value = "";

  els.editDrawer.classList.remove("hidden");
  els.drawerBackdrop.classList.remove("hidden");
}

function closeDrawer() {
  els.editDrawer.classList.add("hidden");
  els.drawerBackdrop.classList.add("hidden");
}

async function submitUpdate(event) {
  event.preventDefault();

  const assetId = Number(document.getElementById("assetId").value);

  const payload = {
    situacao_campo: document.getElementById("editSituation").value,
    data_proxima_revisao: document.getElementById("editNextReview").value,
    responsavel_manutencao: document.getElementById("editMaintenanceOwner").value,
    observacao: document.getElementById("editObservation").value,
  };

  await api(`/api/assets/${assetId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const fileInput = document.getElementById("editFile");

  if (fileInput.files.length > 0) {
    const form = new FormData();
    form.append("file", fileInput.files[0]);

    await fetch(`/api/assets/${assetId}/attachments`, {
      method: "POST",
      body: form,
    });

    fileInput.value = "";
  }

  closeDrawer();

  await refreshAll();
}

function bindNavigation() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-button").forEach((item) => {
        item.classList.remove("active");
      });

      document.querySelectorAll(".page").forEach((page) => {
        page.classList.remove("active");
      });

      button.classList.add("active");

      document.getElementById(button.dataset.page).classList.add("active");

      if (button.dataset.page === "eventsPage") {
        loadEvents();
      }

      if (map) {
        setTimeout(() => map.invalidateSize(), 250);
      }
    });
  });
}

function bindFilters() {
  [
    els.filterView,
    els.filterProduct,
    els.filterState,
    els.filterOwner,
    els.filterReview,
    els.filterFieldStatus,
    els.filterStage,
    els.filterSearch,
  ].forEach((element) => {
    element.addEventListener("input", loadPoints);
  });
}

async function refreshAll() {
  await loadSummary();
  await loadPoints();
  await loadEvents();
}

function exportKml() {
  window.open(`/api/export/kml?${queryString()}`, "_blank");
}

async function boot() {
  initMap();

  await loadOptions();

  bindFilters();
  bindNavigation();

  document.getElementById("refreshBtn").addEventListener("click", refreshAll);

  document.getElementById("exportKmlBtn").addEventListener("click", exportKml);

  document.getElementById("syncBtn").addEventListener("click", async () => {
    await api("/api/pipedrive/sync", {
      method: "POST",
    });

    await refreshAll();

    alert("Sincronização mockada executada.");
  });

  document.getElementById("closeDrawer").addEventListener("click", closeDrawer);

  els.drawerBackdrop.addEventListener("click", closeDrawer);

  document.getElementById("updateForm").addEventListener("submit", submitUpdate);

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";

  try {
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws`);

    ws.onmessage = () => {
      refreshAll();
    };
  } catch (error) {
    console.warn("WebSocket indisponível", error);
  }

  await refreshAll();
}

boot().catch((error) => {
  console.error(error);
  alert("Erro ao carregar plataforma. Veja o console do navegador.");
});