document.addEventListener('DOMContentLoaded', () => {
    // Format Rupiah
    const formatRp = (angka) => {
        return new Intl.NumberFormat('id-ID', {
            style: 'currency',
            currency: 'IDR',
            minimumFractionDigits: 0
        }).format(angka);
    };

    // Elements
    const optimizerForm = document.getElementById('optimizer-form');
    const loadingOverlay = document.getElementById('loading-overlay');
    const errorBanner = document.getElementById('error-banner');
    const errorText = document.getElementById('error-text');
    
    const resCost = document.getElementById('res-cost');
    const resKcal = document.getElementById('res-kcal');
    const resProtein = document.getElementById('res-protein');
    const recommendationsTableBody = document.querySelector('#recommendations-table tbody');
    const commoditySelect = document.getElementById('commodity-select');
    
    // Savings Elements
    const savingsSection = document.getElementById('savings-section');
    const savePortion = document.getElementById('save-portion');
    const saveDay = document.getElementById('save-day');
    const saveMonth = document.getElementById('save-month');
    const saveYear = document.getElementById('save-year');
    
    let costChartInstance = null;
    let trendChartInstance = null;
    let priceDataGlobal = null;

    // Load Prices on startup
    const loadPrices = async () => {
        try {
            console.log("Fetching price data...");
            const response = await fetch('/api/prices');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            const data = await response.json();
            console.log("Price data received:", data);
            
            if (!data.prices || Object.keys(data.prices).length === 0) {
                throw new Error("Data harga kosong dari server.");
            }

            priceDataGlobal = data.prices;
            
            // Populate select
            commoditySelect.innerHTML = '<option value="">-- Pilih Komoditas --</option>';
            const commodities = Object.keys(priceDataGlobal).sort();
            
            commodities.forEach(commodity => {
                const option = document.createElement('option');
                option.value = commodity;
                option.textContent = commodity;
                commoditySelect.appendChild(option);
            });
            
            // Render first commodity by default
            if (commodities.length > 0) {
                commoditySelect.value = commodities[0];
                renderTrendChart(commodities[0]);
            }
            
        } catch (error) {
            console.error("Failed to load prices:", error);
            commoditySelect.innerHTML = `<option value="">Error: ${error.message}</option>`;
            errorText.innerText = "Gagal memuat data harga komoditas. Pastikan server berjalan dengan benar.";
            errorBanner.classList.remove('hidden');
        }
    };

    // Render Trend Chart
    const renderTrendChart = (commodity) => {
        if (!commodity || !priceDataGlobal || !priceDataGlobal[commodity]) return;

        const data = priceDataGlobal[commodity];
        const ctx = document.getElementById('priceTrendChart').getContext('2d');
        
        const labels = [...data.historical_dates, data.predicted_date];
        const historicalPrices = [...data.historical_prices, null];
        const predictedPrices = new Array(data.historical_dates.length).fill(null);
        predictedPrices.push(data.predicted_price);
        
        if (data.historical_prices.length > 0) {
            predictedPrices[data.historical_prices.length - 1] = data.historical_prices[data.historical_prices.length - 1];
        }

        if (trendChartInstance) trendChartInstance.destroy();

        Chart.defaults.color = '#6b7280';
        Chart.defaults.font.family = "'Inter', sans-serif";

        trendChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Harga Historis (7 Hari)',
                        data: historicalPrices,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 3,
                        tension: 0.3,
                        fill: true,
                        pointRadius: 4,
                        pointBackgroundColor: '#10b981'
                    },
                    {
                        label: 'Prediksi XGBoost (H+1)',
                        data: predictedPrices,
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        borderWidth: 3,
                        borderDash: [5, 5],
                        tension: 0.3,
                        fill: false,
                        pointRadius: 6,
                        pointBackgroundColor: '#f59e0b'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top', labels: { usePointStyle: true, boxWidth: 6 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${formatRp(ctx.parsed.y)}`
                        }
                    }
                },
                scales: {
                    y: { 
                        beginAtZero: false,
                        ticks: { callback: (val) => formatRp(val) },
                        grid: { color: '#f3f4f6' }
                    },
                    x: { grid: { display: false } }
                }
            }
        });
    };

    commoditySelect.addEventListener('change', (e) => renderTrendChart(e.target.value));

    // Render Pie Chart
    const renderChart = (recommendations) => {
        const ctx = document.getElementById('costChart').getContext('2d');
        const labels = recommendations.map(r => r.item);
        const data = recommendations.map(r => r.cost);
        const colors = ['#10b981', '#3b82f6', '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f59e0b', '#14b8a6'];

        if (costChartInstance) costChartInstance.destroy();

        costChartInstance = new Chart(ctx, {
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
                cutout: '70%',
                plugins: {
                    legend: { position: 'right', labels: { boxWidth: 12, padding: 15 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.label}: ${formatRp(ctx.parsed)}`
                        }
                    }
                }
            }
        });
    };

    // Handle Optimization
    optimizerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorBanner.classList.add('hidden');
        loadingOverlay.classList.remove('hidden');
        
        const payload = {
            target_kcal: parseFloat(document.getElementById('target-kcal').value) || 0,
            target_protein: parseFloat(document.getElementById('target-protein').value) || 0,
            max_budget: parseFloat(document.getElementById('max-budget').value) || 0
        };

        try {
            const response = await fetch('/api/optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (data.status === 'success') {
                resCost.innerText = formatRp(data.total_cost);
                resKcal.innerText = `${data.total_kcal} Kcal`;
                resProtein.innerText = `${data.total_protein} g`;

                // Savings Logic
                const initialBudget = parseFloat(document.getElementById('initial-budget').value) || 0;
                const targetPortions = parseFloat(document.getElementById('target-portions').value) || 0;
                const activeDays = parseFloat(document.getElementById('active-days').value) || 0;

                const savingPerPortion = initialBudget - data.total_cost;
                if (savingPerPortion > 0) {
                    const savingPerDay = savingPerPortion * targetPortions;
                    const savingPerMonth = savingPerDay * activeDays;
                    savePortion.innerText = formatRp(savingPerPortion);
                    saveDay.innerText = formatRp(savingPerDay);
                    saveMonth.innerText = formatRp(savingPerMonth);
                    saveYear.innerText = formatRp(savingPerMonth * 12);

                    const perc = initialBudget > 0 ? ((savingPerPortion / initialBudget) * 100).toFixed(1) : 0;
                    document.getElementById('perc-portion').innerText = `${perc}% Lebih Hemat`;
                    document.getElementById('perc-day').innerText = `${perc}% Lebih Hemat`;
                    document.getElementById('perc-month').innerText = `${perc}% Lebih Hemat`;
                    document.getElementById('perc-year').innerText = `${perc}% Lebih Hemat`;
                    
                    savingsSection.style.display = 'grid';
                } else {
                    savingsSection.style.display = 'none';
                }

                recommendationsTableBody.innerHTML = '';
                data.recommendations.forEach(r => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${r.item}</strong></td>
                        <td>${r.qty_grams} g</td>
                        <td>${r.kcal}</td>
                        <td>${r.protein}</td>
                        <td>${formatRp(r.cost)}</td>
                    `;
                    recommendationsTableBody.appendChild(tr);
                });

                renderChart(data.recommendations);
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            errorText.innerText = error.message;
            errorBanner.classList.remove('hidden');
        } finally {
            loadingOverlay.classList.add('hidden');
        }
    });

    loadPrices();
});
