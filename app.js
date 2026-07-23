// app.js

// ── STATE VARIABLES ──────────────────────────────────
let races = [];
let currentSeason = 2026;
let currentRace = null;
let activeDrivers = []; // Current list of drivers in the editor
let originalDrivers = []; // Backup of original qualifying order
let currentPredictions = [];
let baselinePredictions = []; // Baseline from original qualifying order
let activeTab = 'race_dashboard';
let chartsLoadedForCombination = { year: null, round: null }; // Track which combination has charts loaded
let predictionDebounceTimer = null;
let raceRefreshTimer = null;
let liveStatusTimer = null;
let selectedDriverCode = null;
let driverWinPieChart = null;
let teamWinPieChart = null;

// ── DOM ELEMENTS ─────────────────────────────────────
const seasonSelect = document.getElementById('season-select');
const raceSelect = document.getElementById('race-select');
const serverStatusIndicator = document.getElementById('server-status-indicator');
const serverStatusText = document.getElementById('server-status-text');
const trackInfo = document.getElementById('track-info');
const trackFlag = document.getElementById('track-flag');
const trackName = document.getElementById('track-name');
const trackCircuit = document.getElementById('track-circuit');
const trackType = document.getElementById('track-type');
const trackLaps = document.getElementById('track-laps');

const gridLoader = document.getElementById('grid-loader');
const driversList = document.getElementById('drivers-list');
const predictBtn = document.getElementById('predict-btn');
const resetGridBtn = document.getElementById('reset-grid-btn');

const predictionEmpty = document.getElementById('prediction-empty');
const predictionLoading = document.getElementById('prediction-loading');
const predictionResultsContent = document.getElementById('prediction-results-content');
const forecastTableBody = document.getElementById('forecast-table-body');
const comparisonGraphBody = document.getElementById('comparison-graph-body');
const quickStatsGrid = document.getElementById('quick-stats-grid');
const driverDetailSelect = document.getElementById('driver-detail-select');
const driverStatsGrid = document.getElementById('driver-stats-grid');
const driverWinPieCanvas = document.getElementById('driver-win-pie');
const teamWinPieCanvas = document.getElementById('team-win-pie');

const p1Name = document.getElementById('p1-name');
const p1Prob = document.getElementById('p1-prob');
const p1Team = document.getElementById('p1-team');
const p1Podium = document.getElementById('podium-1');

const p2Name = document.getElementById('p2-name');
const p2Prob = document.getElementById('p2-prob');
const p2Team = document.getElementById('p2-team');
const p2Podium = document.getElementById('podium-2');

const p3Name = document.getElementById('p3-name');
const p3Prob = document.getElementById('p3-prob');
const p3Team = document.getElementById('p3-team');
const p3Podium = document.getElementById('podium-3');

const generateChartsBtn = document.getElementById('generate-charts-btn');
const chartsLoadingBanner = document.getElementById('charts-loading-banner');
const chartPlaceholder = document.getElementById('chart-placeholder');
const chartIframe = document.getElementById('chart-iframe');
const tabButtons = document.querySelectorAll('.tab-btn');

// ── HELPER FUNCTIONS ─────────────────────────────────
function getTeamClass(team) {
    if (!team) return "";
    const t = team.toLowerCase();
    if (t.includes("red bull")) return "team-red-bull";
    if (t.includes("ferrari")) return "team-ferrari";
    if (t.includes("mercedes")) return "team-mercedes";
    if (t.includes("mclaren")) return "team-mclaren";
    if (t.includes("aston martin")) return "team-aston-martin";
    if (t.includes("alpine")) return "team-alpine";
    if (t.includes("williams")) return "team-williams";
    if (t.includes("rb") || t.includes("racing bulls")) return "team-rb";
    if (t.includes("sauber") || t.includes("kick")) return "team-kick-sauber";
    if (t.includes("haas")) return "team-haas";
    return "";
}

function getTeamColor(team) {
    const defaultColor = "#888888";
    if (!team) return defaultColor;
    const t = team.toLowerCase();
    if (t.includes("red bull")) return "#3671C6";
    if (t.includes("ferrari")) return "#E8002D";
    if (t.includes("mercedes")) return "#27F4D2";
    if (t.includes("mclaren")) return "#FF8000";
    if (t.includes("aston martin")) return "#229971";
    if (t.includes("alpine")) return "#FF87BC";
    if (t.includes("williams")) return "#64C4FF";
    if (t.includes("rb") || t.includes("racing bulls")) return "#6692FF";
    if (t.includes("sauber") || t.includes("kick")) return "#52E252";
    if (t.includes("haas")) return "#B6BABD";
    return defaultColor;
}

function destroyInsightCharts() {
    if (driverWinPieChart) {
        driverWinPieChart.destroy();
        driverWinPieChart = null;
    }
    if (teamWinPieChart) {
        teamWinPieChart.destroy();
        teamWinPieChart = null;
    }
}

function formatStatValue(value, suffix = "") {
    if (typeof value === "number") {
        return Number.isInteger(value) ? `${value}${suffix}` : `${value.toFixed(1)}${suffix}`;
    }
    return `${value}${suffix}`;
}

function renderQuickStats(predictions) {
    if (!quickStatsGrid || !predictions?.length) return;

    const favorite = predictions[0];
    const avgGrid = predictions.reduce((sum, d) => sum + d.grid, 0) / predictions.length;
    const avgPred = predictions.reduce((sum, d) => sum + d.predicted_pos, 0) / predictions.length;
    const gridUpsets = predictions.filter(d => d.grid - d.rank >= 3).length;

    const stats = [
        { label: "Favorite", value: `${favorite.driver} (${favorite.win_prob}%)` },
        { label: "Top Team", value: favorite.team },
        { label: "Driver Count", value: predictions.length },
        { label: "Avg Start Grid", value: avgGrid.toFixed(1) },
        { label: "Avg Pred Finish", value: avgPred.toFixed(1) },
        { label: "Big Movers (3+)", value: gridUpsets }
    ];

    quickStatsGrid.innerHTML = "";
    stats.forEach(item => {
        const card = document.createElement("div");
        card.className = "stat-pill";
        card.innerHTML = `
            <span class="stat-pill-label">${item.label}</span>
            <span class="stat-pill-value">${item.value}</span>
        `;
        quickStatsGrid.appendChild(card);
    });
}

function renderPieInsights(predictions) {
    if (typeof Chart === "undefined" || !driverWinPieCanvas || !teamWinPieCanvas || !predictions?.length) return;
    destroyInsightCharts();

    const topDrivers = [...predictions].slice(0, 10);
    driverWinPieChart = new Chart(driverWinPieCanvas, {
        type: "pie",
        data: {
            labels: topDrivers.map(d => d.driver),
            datasets: [{
                data: topDrivers.map(d => d.win_prob),
                backgroundColor: topDrivers.map(d => getTeamColor(d.team)),
                borderColor: "#101018",
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: "bottom", labels: { color: "#d7d9e4" } }
            }
        }
    });

    const teamMap = {};
    predictions.forEach(d => {
        if (!teamMap[d.team]) teamMap[d.team] = 0;
        teamMap[d.team] += d.win_prob;
    });

    const teamRows = Object.entries(teamMap)
        .map(([team, prob]) => ({ team, prob: +prob.toFixed(2) }))
        .sort((a, b) => b.prob - a.prob);

    teamWinPieChart = new Chart(teamWinPieCanvas, {
        type: "doughnut",
        data: {
            labels: teamRows.map(row => row.team),
            datasets: [{
                data: teamRows.map(row => row.prob),
                backgroundColor: teamRows.map(row => getTeamColor(row.team)),
                borderColor: "#101018",
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            cutout: "58%",
            plugins: {
                legend: { position: "bottom", labels: { color: "#d7d9e4" } }
            }
        }
    });
}

function renderDriverStats(predictions) {
    if (!driverStatsGrid || !predictions?.length) return;

    const selected = predictions.find(d => d.driver === selectedDriverCode) || predictions[0];
    selectedDriverCode = selected.driver;

    const stats = [
        ["Driver", `${selected.fullName} (${selected.driver})`],
        ["Team", selected.team],
        ["Starting Grid", `P${selected.grid}`],
        ["Predicted Finish", `P${selected.predicted_pos}`],
        ["Current Simulation Rank", `#${selected.rank}`],
        ["Win Probability", `${selected.win_prob}%`],
        ["Grid vs Rank Delta", `${selected.grid - selected.rank}`],
        ["Recent Avg Finish", formatStatValue(selected.recent_avg_finish)],
        ["Recent Avg Grid", formatStatValue(selected.recent_avg_grid)],
        ["Driver Cumulative Points", formatStatValue(selected.cum_points)],
        ["Driver Cumulative Wins", formatStatValue(selected.cum_wins)],
        ["Team Cumulative Points", formatStatValue(selected.team_cum_points)],
        ["Team Recent Avg Finish", formatStatValue(selected.team_recent_avg_finish)],
        ["Circuit Type", selected.circuit_type],
        ["Circuit Code", formatStatValue(selected.circuit_type_code)]
    ];

    driverStatsGrid.innerHTML = "";
    stats.forEach(([label, value]) => {
        const item = document.createElement("div");
        item.className = "driver-stat-item";
        item.innerHTML = `
            <span class="driver-stat-label">${label}</span>
            <span class="driver-stat-value">${value}</span>
        `;
        driverStatsGrid.appendChild(item);
    });
}

function renderDriverSelector(predictions) {
    if (!driverDetailSelect || !predictions?.length) return;

    const existing = new Set(predictions.map(d => d.driver));
    if (!selectedDriverCode || !existing.has(selectedDriverCode)) {
        selectedDriverCode = predictions[0].driver;
    }

    driverDetailSelect.innerHTML = "";
    predictions.forEach(d => {
        const option = document.createElement("option");
        option.value = d.driver;
        option.textContent = `${d.driver} - ${d.fullName}`;
        if (d.driver === selectedDriverCode) option.selected = true;
        driverDetailSelect.appendChild(option);
    });
}

function renderInteractiveInsights(predictions) {
    renderQuickStats(predictions);
    renderPieInsights(predictions);
    renderDriverSelector(predictions);
    renderDriverStats(predictions);
}

function clearInteractiveInsights() {
    destroyInsightCharts();
    if (quickStatsGrid) quickStatsGrid.innerHTML = "";
    if (driverStatsGrid) driverStatsGrid.innerHTML = "";
    if (driverDetailSelect) driverDetailSelect.innerHTML = "";
}

function rebuildRaceOptions(selectedRound = null) {
    raceSelect.innerHTML = '<option value="" disabled selected>-- Select a Race --</option>';
    const nextRace = races.find(r => !r.completed);

    races.forEach(race => {
        const opt = document.createElement('option');
        opt.value = race.round;

        let suffix = "";
        if (!race.completed) {
            suffix = (nextRace && nextRace.round === race.round) ? " (Next Race 🔮)" : " (Upcoming)";
        } else {
            suffix = " (Completed)";
        }

        opt.textContent = `Round ${race.round}: ${race.flag} ${race.name} GP${suffix}`;
        raceSelect.appendChild(opt);
    });

    if (selectedRound) {
        raceSelect.value = String(selectedRound);
    }
}

function updateChartsAvailabilityByRace() {
    if (!currentRace) return;

    if (!currentRace.completed) {
        generateChartsBtn.setAttribute('disabled', 'true');
        generateChartsBtn.title = "Analytics charts cannot be generated for future races.";
        chartPlaceholder.className = 'chart-placeholder-state';
        chartPlaceholder.innerHTML = `
            <i class="fa-solid fa-chart-bar placeholder-icon"></i>
            <h3>Future Race Selected</h3>
            <p>Interactive telemetry, lap pace, and tyre strategy charts will be available once the race weekend completes.</p>
        `;
        chartIframe.classList.add('hidden');
        chartPlaceholder.classList.remove('hidden');
    } else {
        generateChartsBtn.removeAttribute('disabled');
        generateChartsBtn.title = "Load or generate analytics charts";
        resetChartPlaceholder();
    }
}

function renderComparisonGraph(predictions) {
    if (!comparisonGraphBody) return;
    if (!predictions || predictions.length === 0) {
        comparisonGraphBody.innerHTML = "";
        return;
    }

    const baselineMap = {};
    baselinePredictions.forEach(p => {
        baselineMap[p.driver] = p.win_prob;
    });

    const sorted = [...predictions]
        .sort((a, b) => b.win_prob - a.win_prob)
        .slice(0, 8);

    comparisonGraphBody.innerHTML = "";

    sorted.forEach(driver => {
        const baselineProb = baselineMap[driver.driver] ?? 0;
        const currentProb = driver.win_prob;
        const delta = +(currentProb - baselineProb).toFixed(1);
        const deltaClass = delta > 0 ? "delta-up" : (delta < 0 ? "delta-down" : "delta-flat");
        const deltaText = delta > 0 ? `+${delta}%` : `${delta}%`;

        const row = document.createElement("div");
        row.className = "comparison-row";
        row.innerHTML = `
            <div class="comparison-driver">${driver.driver}</div>
            <div class="comparison-bars">
                <div class="bar-group">
                    <span class="bar-label">Base</span>
                    <div class="bar-track">
                        <div class="bar-fill base" style="width:${Math.max(0, Math.min(100, baselineProb))}%;"></div>
                    </div>
                    <span class="bar-value">${baselineProb.toFixed(1)}%</span>
                </div>
                <div class="bar-group">
                    <span class="bar-label">Now</span>
                    <div class="bar-track">
                        <div class="bar-fill now" style="width:${Math.max(0, Math.min(100, currentProb))}%; background:${getTeamColor(driver.team)};"></div>
                    </div>
                    <span class="bar-value">${currentProb.toFixed(1)}%</span>
                </div>
            </div>
            <div class="comparison-delta ${deltaClass}">${deltaText}</div>
        `;
        comparisonGraphBody.appendChild(row);
    });
}

async function pollLiveStatus() {
    try {
        const response = await fetch("/api/live_status");
        const data = await response.json();
        if (data.status === "success") {
            serverStatusIndicator.classList.remove("offline");
            serverStatusIndicator.classList.add("online");
            serverStatusText.textContent = "LIVE UPDATES ACTIVE";
        } else {
            throw new Error(data.message || "Live status unavailable");
        }
    } catch (e) {
        serverStatusIndicator.classList.remove("online");
        serverStatusIndicator.classList.add("offline");
        serverStatusText.textContent = "LIVE UPDATES OFFLINE";
    }
}

async function refreshRaceMetadata() {
    if (!currentSeason) return;

    try {
        const response = await fetch(`/api/races?year=${currentSeason}`);
        const latestRaces = await response.json();
        if (!Array.isArray(latestRaces) || latestRaces.length === 0) return;

        const selectedRound = currentRace ? currentRace.round : parseInt(raceSelect.value);
        races = latestRaces;
        rebuildRaceOptions(selectedRound);

        if (selectedRound) {
            const updatedRace = races.find(r => r.round === selectedRound);
            if (updatedRace) {
                currentRace = updatedRace;
                trackFlag.textContent = currentRace.flag;
                trackName.textContent = `${currentRace.name} Grand Prix`;
                trackCircuit.textContent = currentRace.circuit;
                trackType.textContent = currentRace.type;
                trackType.className = `meta-value badge-${currentRace.type}`;
                updateChartsAvailabilityByRace();
            }
        }
    } catch (e) {
        console.error("Background race refresh failed:", e);
    }
}

function queueAutoPrediction() {
    if (!currentRace || !activeDrivers.length) return;
    if (predictionDebounceTimer) clearTimeout(predictionDebounceTimer);
    predictionDebounceTimer = setTimeout(() => {
        runPrediction();
    }, 500);
}

// ── INITIALIZATION ───────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
    try {
        // Setup Season select listener
        if (seasonSelect) {
            currentSeason = parseInt(seasonSelect.value);
            seasonSelect.addEventListener('change', async (e) => {
                currentSeason = parseInt(e.target.value);
                await loadRacesForSeason(currentSeason);
            });
        }

        // Add race select change listener
        raceSelect.addEventListener('change', handleRaceChange);
        
        // Setup Grid buttons
        resetGridBtn.addEventListener('click', resetGridOrder);
        predictBtn.addEventListener('click', runPrediction);
        
        // Setup Chart generation
        generateChartsBtn.addEventListener('click', generatePlotlyCharts);

        if (driverDetailSelect) {
            driverDetailSelect.addEventListener('change', (e) => {
                selectedDriverCode = e.target.value;
                renderDriverStats(currentPredictions);
            });
        }

        // Setup Tab listeners
        tabButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                tabButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                activeTab = btn.getAttribute('data-tab');
                loadChartInIframe();
            });
        });

        // Load default season
        await loadRacesForSeason(currentSeason);
        await pollLiveStatus();

        if (raceRefreshTimer) clearInterval(raceRefreshTimer);
        raceRefreshTimer = setInterval(refreshRaceMetadata, 30000);

        if (liveStatusTimer) clearInterval(liveStatusTimer);
        liveStatusTimer = setInterval(pollLiveStatus, 30000);

    } catch (e) {
        console.error("Error loading initial data:", e);
        alert("Failed to connect to the backend server. Make sure server.py is running!");
    }
});

// ── LOAD RACES FOR SEASON ───────────────────────────
async function loadRacesForSeason(season) {
    try {
        raceSelect.innerHTML = '<option value="" disabled selected>Loading races...</option>';
        trackInfo.classList.add('hidden');
        generateChartsBtn.setAttribute('disabled', 'true');
        resetChartPlaceholder();
        
        const response = await fetch(`/api/races?year=${season}`);
        races = await response.json();
        
        rebuildRaceOptions();

        // Find the first uncompleted race (the next race)
        let nextRace = races.find(r => !r.completed);
        
        // Auto-select the target race
        if (nextRace) {
            raceSelect.value = nextRace.round;
            handleRaceSelected(nextRace.round);
        } else if (races.length > 0) {
            // If all races are completed, select the last round
            const lastRound = races[races.length - 1].round;
            raceSelect.value = lastRound;
            handleRaceSelected(lastRound);
        }
    } catch (e) {
        console.error("Error loading races for season:", e);
        alert("Failed to load calendar for season " + season);
    }
}

// ── EVENT HANDLERS ───────────────────────────────────
async function handleRaceChange(e) {
    const round = parseInt(e.target.value);
    handleRaceSelected(round);
}

async function handleRaceSelected(round) {
    currentRace = races.find(r => r.round === round);
    baselinePredictions = [];
    currentPredictions = [];
    selectedDriverCode = null;
    clearInteractiveInsights();
    
    if (!currentRace) return;

    // 1. Show track info banner
    trackFlag.textContent = currentRace.flag;
    trackName.textContent = `${currentRace.name} Grand Prix`;
    trackCircuit.textContent = currentRace.circuit;
    
    // Configure badge styling
    trackType.textContent = currentRace.type;
    trackType.className = `meta-value badge-${currentRace.type}`;
    
    trackLaps.textContent = currentRace.round === 8 ? "78 Laps" : "50+ Laps";
    
    trackInfo.classList.remove('hidden');

    // Enable/disable charts button based on race completion status
    updateChartsAvailabilityByRace();

    // 2. Fetch original grid order & initial prediction
    loadGridAndPredict(round);
}

async function loadGridAndPredict(round) {
    gridLoader.classList.remove('hidden');
    driversList.classList.add('hidden');
    predictBtn.setAttribute('disabled', 'true');
    resetGridBtn.setAttribute('disabled', 'true');
    
    // Reset prediction card states
    predictionResultsContent.classList.add('hidden');
    predictionLoading.classList.add('hidden');
    predictionEmpty.classList.remove('hidden');
    clearInteractiveInsights();
    
    try {
        const response = await fetch(`/api/predict?year=${currentSeason}&round=${round}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            // Sort drivers by grid position
            activeDrivers = [...data.predictions].sort((a, b) => a.grid - b.grid);
            originalDrivers = JSON.parse(JSON.stringify(activeDrivers)); // Deep clone backup
            baselinePredictions = JSON.parse(JSON.stringify(data.predictions));
            currentPredictions = [...data.predictions];
            
            renderGridEditor();
            
            // Auto run first prediction so they see initial state
            displayPredictions(data.predictions);
        } else {
            driversList.innerHTML = `<div class="error-msg">Error loading drivers: ${data.message}</div>`;
        }
    } catch (err) {
        console.error(err);
        driversList.innerHTML = `<div class="error-msg">Failed to connect to simulation API</div>`;
    } finally {
        gridLoader.classList.add('hidden');
        driversList.classList.remove('hidden');
        predictBtn.removeAttribute('disabled');
        resetGridBtn.removeAttribute('disabled');
    }
}

// Render the interactive drivers list with up/down arrows
function renderGridEditor() {
    driversList.innerHTML = '';
    
    activeDrivers.forEach((driver, idx) => {
        const item = document.createElement('div');
        item.className = `driver-grid-item ${getTeamClass(driver.team)}`;
        
        const isFirst = idx === 0;
        const isLast = idx === activeDrivers.length - 1;
        
        item.innerHTML = `
            <div class="grid-pos-badge">P${idx + 1}</div>
            <div class="driver-main-info">
                <div class="driver-abbrev-row">
                    <span class="driver-code">${driver.driver}</span>
                    <span class="driver-fname">${driver.fullName}</span>
                </div>
                <span class="driver-team-name">${driver.team}</span>
            </div>
            <div class="grid-controls">
                <button class="btn-arrow btn-up" data-index="${idx}" ${isFirst ? 'disabled' : ''} title="Move Up">
                    <i class="fa-solid fa-chevron-up"></i>
                </button>
                <button class="btn-arrow btn-down" data-index="${idx}" ${isLast ? 'disabled' : ''} title="Move Down">
                    <i class="fa-solid fa-chevron-down"></i>
                </button>
            </div>
        `;
        
        driversList.appendChild(item);
    });
    
    // Add event listeners to arrows
    document.querySelectorAll('.btn-up').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = parseInt(e.currentTarget.getAttribute('data-index'));
            swapDrivers(idx, idx - 1);
        });
    });
    
    document.querySelectorAll('.btn-down').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = parseInt(e.currentTarget.getAttribute('data-index'));
            swapDrivers(idx, idx + 1);
        });
    });
}

function swapDrivers(indexA, indexB) {
    // Swap items in array
    const temp = activeDrivers[indexA];
    activeDrivers[indexA] = activeDrivers[indexB];
    activeDrivers[indexB] = temp;
    
    // Update grid_pos values to match their new list index
    activeDrivers.forEach((d, idx) => {
        d.grid = idx + 1;
    });
    
    renderGridEditor();
    queueAutoPrediction();
}

function resetGridOrder() {
    activeDrivers = JSON.parse(JSON.stringify(originalDrivers));
    renderGridEditor();
    queueAutoPrediction();
}

// ── RUN AI SIMULATION ────────────────────────────────
async function runPrediction() {
    if (!currentRace) return;
    
    predictBtn.setAttribute('disabled', 'true');
    resetGridBtn.setAttribute('disabled', 'true');
    predictionEmpty.classList.add('hidden');
    predictionResultsContent.classList.add('hidden');
    predictionLoading.classList.remove('hidden');

    // Build the grid mapping to send to the backend
    const gridOverride = {};
    activeDrivers.forEach((driver, idx) => {
        gridOverride[driver.driver] = idx + 1;
    });

    try {
        const gridParam = encodeURIComponent(JSON.stringify(gridOverride));
        const url = `/api/predict?year=${currentSeason}&round=${currentRace.round}&grid=${gridParam}`;
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.status === 'success') {
            displayPredictions(data.predictions);
        } else {
            alert(`Error running simulation: ${data.message}`);
            predictionEmpty.classList.remove('hidden');
        }
    } catch (e) {
        console.error(e);
        alert('Server connection timed out.');
        predictionEmpty.classList.remove('hidden');
    } finally {
        predictionLoading.classList.add('hidden');
        predictBtn.removeAttribute('disabled');
        resetGridBtn.removeAttribute('disabled');
    }
}

// Render the 3D Podium and Forecast Table
function displayPredictions(predictions) {
    if (!predictions || predictions.length < 3) return;
    if (!baselinePredictions || baselinePredictions.length === 0) {
        baselinePredictions = JSON.parse(JSON.stringify(predictions));
    }
    currentPredictions = [...predictions];

    // ── 1. PODIUM RENDER ─────────────────────────────
    const p1 = predictions[0];
    const p2 = predictions[1];
    const p3 = predictions[2];

    p1Name.textContent = p1.driver;
    p1Prob.textContent = `${p1.win_prob}%`;
    p1Team.textContent = p1.team;
    p1Podium.className = `podium-step step-1 glow-${getTeamClass(p1.team).replace('team-', '')}`;
    p1Podium.querySelector('.podium-block').style.borderTopColor = getTeamColor(p1.team);
    
    p2Name.textContent = p2.driver;
    p2Prob.textContent = `${p2.win_prob}%`;
    p2Team.textContent = p2.team;
    p2Podium.className = `podium-step step-2`;
    p2Podium.querySelector('.podium-block').style.borderTopColor = getTeamColor(p2.team);
    
    p3Name.textContent = p3.driver;
    p3Prob.textContent = `${p3.win_prob}%`;
    p3Team.textContent = p3.team;
    p3Podium.className = `podium-step step-3`;
    p3Podium.querySelector('.podium-block').style.borderTopColor = getTeamColor(p3.team);

    // ── 2. TABLE RENDER ──────────────────────────────
    forecastTableBody.innerHTML = '';
    
    predictions.forEach((driver) => {
        const row = document.createElement('tr');
        
        // Calculate position delta (grid position vs predicted rank)
        const grid = driver.grid;
        const predRank = driver.rank;
        const delta = grid - predRank;
        
        let deltaHtml = '';
        if (delta > 0) {
            deltaHtml = `<span class="grid-change-indicator change-up"><i class="fa-solid fa-caret-up"></i> +${delta}</span>`;
        } else if (delta < 0) {
            deltaHtml = `<span class="grid-change-indicator change-down"><i class="fa-solid fa-caret-down"></i> ${delta}</span>`;
        } else {
            deltaHtml = `<span class="grid-change-indicator change-none">=</span>`;
        }

        const teamColor = getTeamColor(driver.team);
        
        row.innerHTML = `
            <td class="col-rank">${driver.rank}</td>
            <td>
                <div class="table-driver-cell">
                    <span class="table-driver-name">${driver.fullName} (${driver.driver})</span>
                    <span class="table-driver-team">${driver.team}</span>
                </div>
            </td>
            <td>P${driver.grid} ${deltaHtml}</td>
            <td class="col-center"><strong>P${driver.predicted_pos}</strong></td>
            <td class="col-right">
                <div class="prob-cell-wrapper">
                    <span class="prob-value-text">${driver.win_prob}%</span>
                    <div class="prob-bar-bg">
                        <div class="prob-bar-fill" style="background-color: ${teamColor}; width: ${driver.win_prob}%"></div>
                    </div>
                </div>
            </td>
        `;
        
        forecastTableBody.appendChild(row);
    });

    predictionResultsContent.classList.remove('hidden');
    renderComparisonGraph(predictions);
    renderInteractiveInsights(predictions);
}

// ── GENERATE & LOAD INTERACTIVE PLOTLY CHARTS ────────
async function generatePlotlyCharts() {
    if (!currentRace || !currentRace.completed) return;
    
    generateChartsBtn.setAttribute('disabled', 'true');
    chartsLoadingBanner.classList.remove('hidden');
    
    // Update placeholder text
    chartPlaceholder.className = 'chart-placeholder-state chart-placeholder-state-loading';
    chartPlaceholder.innerHTML = `
        <div class="spinner-dual"></div>
        <h3 class="mt-3">Generating Interactive Charts...</h3>
        <p>Connecting to FastF1, loading race telemetry, and writing Plotly graphics. This takes about 30 seconds for new races, but is instant for cached events!</p>
    `;

    try {
        const response = await fetch(`/api/generate_charts?year=${currentSeason}&round=${currentRace.round}`);
        const data = await response.json();
        
        if (data.status === 'success') {
            chartsLoadedForCombination = { year: currentSeason, round: currentRace.round };
            
            // Show success banner briefly
            chartsLoadingBanner.className = 'charts-status-banner bg-success';
            chartsLoadingBanner.innerHTML = `
                <div class="banner-content">
                    <i class="fa-solid fa-circle-check"></i>
                    <span>Charts successfully loaded for the ${currentRace.name} GP!</span>
                </div>
            `;
            
            setTimeout(() => {
                chartsLoadingBanner.classList.add('hidden');
                chartsLoadingBanner.className = 'charts-status-banner hidden bg-warning';
            }, 3000);

            // Load the chart in iframe
            loadChartInIframe();
        } else {
            alert(`Plotly chart rendering failed: ${data.message}`);
            resetChartPlaceholder();
        }
    } catch (e) {
        console.error(e);
        alert('Chart generation request failed. Check server status.');
        resetChartPlaceholder();
    } finally {
        generateChartsBtn.removeAttribute('disabled');
    }
}

function resetChartPlaceholder() {
    if (currentRace && !currentRace.completed) {
        chartPlaceholder.className = 'chart-placeholder-state';
        chartPlaceholder.innerHTML = `
            <i class="fa-solid fa-chart-bar placeholder-icon"></i>
            <h3>Future Race Selected</h3>
            <p>Interactive telemetry, lap pace, and tyre strategy charts will be available once the race weekend completes.</p>
        `;
    } else {
        chartPlaceholder.className = 'chart-placeholder-state';
        chartPlaceholder.innerHTML = `
            <i class="fa-solid fa-chart-bar placeholder-icon"></i>
            <h3>No Interactive Charts Loaded</h3>
            <p>Select a Grand Prix and click "Load/Generate Charts" above to build the telemetry maps and lap graphs.</p>
        `;
    }
    chartIframe.classList.add('hidden');
    chartPlaceholder.classList.remove('hidden');
}

function loadChartInIframe() {
    if (!currentRace || chartsLoadedForCombination.year !== currentSeason || chartsLoadedForCombination.round !== currentRace.round) {
        // Charts not generated yet for this combination
        resetChartPlaceholder();
        return;
    }

    // Map tab names to actual html files generated in data/charts/
    const tabFiles = {
        'race_dashboard': 'race_dashboard.html',
        'lap_times': 'lap_times.html',
        'tyre_strategy': 'tyre_strategy.html',
        'tyre_degradation': 'tyre_degradation.html',
        'team_pace': 'team_pace.html',
        'position_changes': 'position_changes.html'
    };

    const fileName = tabFiles[activeTab] || 'race_dashboard.html';
    
    // Add cache-busting parameter to force reload the iframe content
    chartIframe.src = `/data/charts/${fileName}?t=${Date.now()}`;
    
    chartPlaceholder.classList.add('hidden');
    chartIframe.classList.remove('hidden');
}
