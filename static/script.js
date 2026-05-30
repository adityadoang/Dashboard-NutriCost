document.addEventListener('DOMContentLoaded', () => {

    // ── Format Rupiah penuh ──
    const fmt = (v) => new Intl.NumberFormat('id-ID', {
        style: 'currency', currency: 'IDR', minimumFractionDigits: 0
    }).format(v);

    // ── Format pintar: singkat miliar/triliun, hover untuk detail ──
    const fmtSmart = (val) => {
        const abs = Math.abs(val);
        if (abs >= 1e12) return `~${(val / 1e12).toFixed(1).replace('.', ',')} Triliun`;
        if (abs >= 1e9) return `~${(val / 1e9).toFixed(1).replace('.', ',')} Miliar`;
        if (abs >= 1e6) return `~${(val / 1e6).toFixed(1).replace('.', ',')} Juta`;
        return fmt(val);
    };

    // Set text with smart format + tooltip detail
    const setSmartValue = (el, val) => {
        el.textContent = fmtSmart(val);
        el.title = fmt(val); // hover untuk lihat angka lengkap
        el.style.cursor = 'help';
    };

    // ── Elements ──
    const form = document.getElementById('optimizer-form');
    const overlay = document.getElementById('loading-overlay');
    const errBanner = document.getElementById('error-banner');
    const errText = document.getElementById('error-text');
    const comSelect = document.getElementById('commodity-select');

    let optCostChart = null, trendChart = null, financialFlowChart = null, priceData = null;

    // ── Chart.js theme ──
    Chart.defaults.color = '#9b9590';
    Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
    Chart.defaults.font.size = 11;

    const warmColors = [
        '#1b6b4d', '#c8842a', '#c25848', '#6a5acd', '#3d8b6a',
        '#d4a843', '#e07b5f', '#5b8fb9', '#8fbc5a', '#b07cc6'
    ];

    const chartTooltip = {
        backgroundColor: '#ffffff',
        titleColor: '#2a2521',
        bodyColor: '#5c5550',
        borderColor: '#e0dbd3',
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
        titleFont: { weight: '700' },
    };

    // ── Nav scroll + IntersectionObserver ──
    const initNav = () => {
        const allLinks = document.querySelectorAll('.nav-link');
        allLinks.forEach(link => {
            link.addEventListener('click', () => {
                const id = link.dataset.section;
                const el = document.getElementById(id);
                if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    allLinks.forEach(l => l.classList.remove('active'));
                    document.querySelectorAll(`[data-section="${id}"]`).forEach(l => l.classList.add('active'));
                }
            });
        });

        const sections = document.querySelectorAll('.section');
        const obs = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (e.isIntersecting) {
                    allLinks.forEach(l => l.classList.remove('active'));
                    document.querySelectorAll(`[data-section="${e.target.id}"]`).forEach(l => l.classList.add('active'));
                }
            });
        }, { rootMargin: '-30% 0px -60% 0px' });
        sections.forEach(s => obs.observe(s));
    };

    // ── Drawer ──
    const initDrawer = () => {
        const drawer = document.getElementById('drawer');
        const backdrop = document.getElementById('drawer-backdrop');
        const open = () => { drawer.classList.add('open'); backdrop.classList.add('open'); };
        const close = () => { drawer.classList.remove('open'); backdrop.classList.remove('open'); };

        document.getElementById('btn-drawer').addEventListener('click', open);
        document.getElementById('btn-close-drawer').addEventListener('click', close);
        backdrop.addEventListener('click', close);

        // Simulasikan radio button untuk checkbox porsi
        const portionCbs = document.querySelectorAll('.portion-cb');
        portionCbs.forEach(cb => {
            cb.addEventListener('change', function () {
                if (this.checked) {
                    portionCbs.forEach(other => {
                        if (other !== this) other.checked = false;
                    });
                } else {
                    // Jangan biarkan semuanya uncheck, paksa tetap check
                    this.checked = true;
                }
            });
        });

        document.getElementById('btn-save-drawer').addEventListener('click', () => {
            const initBudgetEl = document.getElementById('d-init-budget');
            if (initBudgetEl) {
                document.getElementById('initial-budget').value = initBudgetEl.value;
                const displayBudget = document.getElementById('display-init-budget');
                if (displayBudget) displayBudget.textContent = fmt(initBudgetEl.value);
            }
            const selectedPortion = document.querySelector('.portion-cb:checked');
            const portionValue = selectedPortion ? selectedPortion.value : 3000;
            document.getElementById('target-portions').value = portionValue;

            // Update the display text on the dashboard
            const displayPortion = document.getElementById('display-target-portions');
            if (displayPortion) displayPortion.textContent = portionValue;

            const activeDaysValue = document.getElementById('d-days').value;
            document.getElementById('active-days').value = activeDaysValue;
            const displayDays = document.getElementById('display-active-days');
            if (displayDays) displayDays.textContent = activeDaysValue;

            close();
        });
    };

    // ── Load Prices ──
    const loadPrices = async () => {
        try {
            const res = await fetch('/api/prices');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (!data.prices || !Object.keys(data.prices).length) throw new Error('Data harga kosong.');

            priceData = data.prices;
            const items = Object.keys(priceData).sort();

            const totalCommoditiesEl = document.getElementById('total-commodities');
            if (totalCommoditiesEl) totalCommoditiesEl.textContent = items.length;

            comSelect.innerHTML = '<option value="">— Pilih Komoditas —</option>';
            items.forEach(c => {
                const o = document.createElement('option');
                o.value = c; o.textContent = c;
                comSelect.appendChild(o);
            });

            if (items.length) { comSelect.value = items[0]; renderTrend(items[0]); }
        } catch (err) {
            console.error(err);
            comSelect.innerHTML = `<option>Error: ${err.message}</option>`;
            errText.innerText = 'Gagal memuat data harga.';
            errBanner.classList.remove('hidden');
        }
    };

    // ── Trend Chart ──
    const renderTrend = (name) => {
        if (!name || !priceData?.[name]) return;
        const d = priceData[name];
        const ctx = document.getElementById('priceTrendChart').getContext('2d');

        const labels = [...d.historical_dates, d.predicted_date];
        const hist = [...d.historical_prices, null];
        const pred = new Array(d.historical_dates.length).fill(null);
        pred.push(d.predicted_price);
        if (d.historical_prices.length) pred[d.historical_prices.length - 1] = d.historical_prices.at(-1);

        const pMin = document.getElementById('price-min');
        const pMax = document.getElementById('price-max');
        const pPred = document.getElementById('price-predicted');
        if (pMin) pMin.textContent = fmt(Math.min(...d.historical_prices));
        if (pMax) pMax.textContent = fmt(Math.max(...d.historical_prices));
        if (pPred) pPred.textContent = fmt(d.predicted_price);

        if (trendChart) trendChart.destroy();

        trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Historis (7 Hari)',
                        data: hist,
                        borderColor: '#1b6b4d',
                        backgroundColor: 'rgba(27,107,77,0.06)',
                        borderWidth: 2.5, tension: 0.35, fill: true,
                        pointRadius: 5, pointBackgroundColor: '#1b6b4d',
                        pointBorderColor: '#ffffff', pointBorderWidth: 2,
                    },
                    {
                        label: 'Prediksi (H+1)',
                        data: pred,
                        borderColor: '#c8842a',
                        backgroundColor: 'rgba(200,132,42,0.06)',
                        borderWidth: 2.5, borderDash: [6, 4], tension: 0.35, fill: false,
                        pointRadius: 7, pointBackgroundColor: '#c8842a',
                        pointBorderColor: '#ffffff', pointBorderWidth: 2,
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { usePointStyle: true, boxWidth: 6, padding: 16 } },
                    tooltip: { ...chartTooltip, callbacks: { label: (c) => `${c.dataset.label}: ${fmt(c.parsed.y)}` } }
                },
                scales: {
                    y: { beginAtZero: false, ticks: { callback: (v) => fmt(v) }, grid: { color: '#eae6df' } },
                    x: { grid: { display: false } }
                }
            }
        });
    };

    comSelect.addEventListener('change', (e) => renderTrend(e.target.value));

    // ── Bar Chart ──
    const renderBarChart = (recs, canvasId) => {
        const ctx = document.getElementById(canvasId).getContext('2d');
        if (optCostChart) optCostChart.destroy();

        let sorted = [...recs].sort((a, b) => b.cost - a.cost);
        let labels = [];
        let data = [];
        let bgColors = [];

        if (sorted.length <= 5) {
            labels = sorted.map(r => r.item);
            data = sorted.map(r => r.cost);
            bgColors = warmColors.slice(0, sorted.length);
        } else {
            const top5 = sorted.slice(0, 5);
            labels = top5.map(r => r.item);
            data = top5.map(r => r.cost);
            bgColors = warmColors.slice(0, 5);

            const sumRest = sorted.slice(5).reduce((acc, r) => acc + r.cost, 0);
            labels.push('Lainnya');
            data.push(sumRest);
            bgColors.push('#eae6df');
        }

        optCostChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: bgColors,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { ...chartTooltip, callbacks: { label: (c) => `Rp ${fmt(c.parsed.y).replace('Rp', '').trim()}` } }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#eae6df' },
                        ticks: { callback: (v) => fmt(v) }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });
    };

    // ── Financial Flow Doughnut Chart ──
    const renderFinancialFlowChart = (flowData) => {
        const ctx = document.getElementById('financialFlowChart').getContext('2d');
        if (financialFlowChart) financialFlowChart.destroy();

        const TARGET_ANAK_NASIONAL = 82000000;

        const sectorMetadata = {
            'Petani Padi (UMKM)': {
                icon: 'fa-solid fa-wheat-awn',
                commodities: ['Beras SPHP Bulog', 'Beras Medium', 'Beras Premium'],
                color: '#1b6b4d'
            },
            'Peternak Unggas (UMKM)': {
                icon: 'fa-solid fa-egg',
                commodities: ['Daging Ayam Ras', 'Telur Ayam Ras'],
                color: '#e53e3e'
            },
            'Peternak Sapi (UMKM)': {
                icon: 'fa-solid fa-cow',
                commodities: ['Daging Sapi Paha Belakang'],
                color: '#c25848'
            },
            'Petani Hortikultura (UMKM)': {
                icon: 'fa-solid fa-pepper-hot',
                commodities: ['Cabai Merah Keriting', 'Cabai Merah Besar', 'Cabai Rawit Merah', 'Bawang Merah', 'Bawang Putih Honan'],
                color: '#6a5acd'
            },
            'Petani Palawija (UMKM)': {
                icon: 'fa-solid fa-seedling',
                commodities: ['Kedelai Impor'],
                color: '#8fbc5a'
            },
            'Industri Pengolahan': {
                icon: 'fa-solid fa-industry',
                commodities: ['Gula Pasir Curah', 'Minyak Goreng Sawit Curah', 'Minyak Goreng Sawit Kemasan Premium', 'Minyakita', 'Tepung Terigu'],
                color: '#d4a843'
            },
            'Lainnya': {
                icon: 'fa-solid fa-ellipsis',
                commodities: ['Komoditas lainnya'],
                color: '#e07b5f'
            }
        };

        // Sort and scale data by value (national daily flow)
        const entries = Object.entries(flowData).map(e => [e[0], e[1] * TARGET_ANAK_NASIONAL]).sort((a, b) => b[1] - a[1]);
        const labels = entries.map(e => e[0]);
        const data = entries.map(e => e[1]);

        const colors = labels.map(label => sectorMetadata[label]?.color || '#e07b5f');

        financialFlowChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { padding: 15, usePointStyle: true, pointStyle: 'circle' }
                    },
                    tooltip: {
                        ...chartTooltip,
                        callbacks: {
                            label: (c) => ` ${c.label}: ${fmtSmart(c.parsed)}`
                        }
                    }
                }
            }
        });

        // Render detail list
        const listContainer = document.getElementById('sector-details-list');
        if (listContainer) {
            listContainer.innerHTML = '';
            entries.forEach(([sector, value]) => {
                const meta = sectorMetadata[sector] || sectorMetadata['Lainnya'];
                const itemEl = document.createElement('div');
                itemEl.className = 'sector-item fade-up';
                itemEl.style.borderLeftColor = meta.color;

                const commodityBadges = meta.commodities
                    .map(c => `<span class="commodity-badge">${c}</span>`)
                    .join('');

                itemEl.innerHTML = `
                    <div class="sector-icon-wrap" style="color: ${meta.color};">
                        <i class="${meta.icon}"></i>
                    </div>
                    <div class="sector-info">
                        <div class="sector-name-row">
                            <span class="sector-name">${sector}</span>
                            <span class="sector-flow-val" title="Aliran dana per porsi: ${fmt(value / TARGET_ANAK_NASIONAL)}">${fmtSmart(value)}/hari</span>
                        </div>
                        <div class="sector-commodities">
                            ${commodityBadges}
                        </div>
                    </div>
                `;
                listContainer.appendChild(itemEl);
            });
        }
    };

    // ── Optimize ──
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errBanner.classList.add('hidden');
        overlay.classList.remove('hidden');

        const payload = {
            target_kcal: parseFloat(document.getElementById('target-kcal').value) || 0,
            target_protein: parseFloat(document.getElementById('target-protein').value) || 0
        };

        try {
            const res = await fetch('/api/optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (data.status === 'success') {
                document.getElementById('opt-stats').style.display = 'grid';
                document.getElementById('opt-results').style.display = 'grid';

                document.getElementById('opt-cost').textContent = fmt(data.total_cost);
                document.getElementById('opt-kcal').textContent = `${data.total_kcal} Kcal`;
                document.getElementById('opt-protein').textContent = `${data.total_protein} g`;

                // ROI and Efficiency Metrics
                const ib = parseFloat(document.getElementById('initial-budget').value) || 0;
                const tp = parseFloat(document.getElementById('target-portions').value) || 0;
                const spp = ib - data.total_cost; // savings per portion

                if (ib > 0) {
                    const spd = spp > 0 ? spp * tp : 0; // surplus hari ini
                    const efisiensi = ((spp / ib) * 100).toFixed(1);
                    const extraPorsi = data.total_cost > 0 && spd > 0 ? Math.floor(spd / data.total_cost) : 0;

                    // Hemat / Porsi
                    setSmartValue(document.getElementById('opt-hemat-porsi'), spp > 0 ? spp : 0);

                    // Sisa Dana Hari Ini
                    setSmartValue(document.getElementById('opt-sisa-dana'), spd);

                    // Efisiensi Biaya
                    document.getElementById('opt-efisiensi').textContent = `${spp > 0 ? efisiensi : 0}%`;
                    document.getElementById('opt-efisiensi').title = `Penghematan dari pagu ${fmt(ib)}`;
                    document.getElementById('opt-efisiensi').style.cursor = 'help';

                    // Potensi Ekstra Porsi
                    const extraPorsiEl = document.getElementById('opt-extra-porsi');
                    if (extraPorsiEl) {
                        const fmtNumber = new Intl.NumberFormat('id-ID').format(extraPorsi);
                        extraPorsiEl.textContent = `${fmtNumber} Porsi`;
                        extraPorsiEl.title = `Bisa memberi makan ${fmtNumber} anak tambahan hari ini!`;
                        extraPorsiEl.style.cursor = 'help';
                    }

                    document.getElementById('savings-section').style.display = 'grid';

                    // Macroeconomic Impact
                    const TARGET_ANAK_NASIONAL = 82000000;

                    const macroSavingsEl = document.getElementById('macro-national-savings');
                    if (spp > 0) {
                        const nationalSavingsDaily = spp * TARGET_ANAK_NASIONAL;
                        macroSavingsEl.textContent = fmtSmart(nationalSavingsDaily);
                        macroSavingsEl.title = `Selisih Rp ${fmt(spp).replace('Rp', '').trim()} × 82 Juta Anak = ${fmt(nationalSavingsDaily)} per hari`;
                        macroSavingsEl.style.cursor = 'help';
                    } else {
                        macroSavingsEl.textContent = "Rp 0 Miliar";
                        macroSavingsEl.title = "Tidak ada penghematan dari pagu";
                    }

                    document.getElementById('macro-section').style.display = 'block';

                } else {
                    document.getElementById('savings-section').style.display = 'none';
                    document.getElementById('macro-section').style.display = 'none';
                }

                // Table
                const tbody = document.querySelector('#recommendations-table tbody');
                tbody.innerHTML = '';
                data.recommendations.forEach((r, i) => {
                    const tr = document.createElement('tr');
                    tr.classList.add('fade-up');
                    tr.style.animationDelay = `${i * 0.04}s`;
                    tr.innerHTML = `
                        <td><strong>${r.item}</strong></td>
                        <td>${r.qty_grams} g</td>
                        <td>${r.kcal}</td>
                        <td>${r.protein}</td>
                        <td>${fmt(r.cost)}</td>`;
                    tbody.appendChild(tr);
                });

                renderBarChart(data.recommendations, 'optCostChart');

                if (data.financial_flow) {
                    renderFinancialFlowChart(data.financial_flow);
                }
            } else { throw new Error(data.message); }
        } catch (err) {
            errText.innerText = err.message;
            errBanner.classList.remove('hidden');
        } finally { overlay.classList.add('hidden'); }
    });

    // ── Auto Calculate Active Days ──
    const getActiveDays = () => {
        const now = new Date();
        const year = now.getFullYear();
        const month = now.getMonth();
        let daysInMonth = new Date(year, month + 1, 0).getDate();
        let activeDays = 0;
        for (let i = 1; i <= daysInMonth; i++) {
            const day = new Date(year, month, i).getDay();
            if (day !== 0 && day !== 6) { // 0 = Sunday, 6 = Saturday
                activeDays++;
            }
        }

        // Update month label
        const monthNames = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
        const monthLabel = document.getElementById('current-month-label');
        if (monthLabel) {
            monthLabel.textContent = `${monthNames[month]} ${year}`;
        }

        return activeDays;
    };
    const autoActiveDays = getActiveDays();
    const dDaysHidden = document.getElementById('d-days');
    if (dDaysHidden) dDaysHidden.value = autoActiveDays;
    const dDaysDrawerDisplay = document.getElementById('d-days-display');
    if (dDaysDrawerDisplay) dDaysDrawerDisplay.textContent = autoActiveDays;
    document.getElementById('active-days').value = autoActiveDays;

    const displayActiveDays = document.getElementById('display-active-days');
    if (displayActiveDays) displayActiveDays.textContent = autoActiveDays;

    const initBudgetHidden = document.getElementById('initial-budget');
    const displayInitBudget = document.getElementById('display-init-budget');
    if (initBudgetHidden && displayInitBudget) {
        displayInitBudget.textContent = fmt(initBudgetHidden.value);
    }

    initNav();
    initDrawer();
    loadPrices();
});
