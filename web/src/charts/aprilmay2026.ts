import { Chart, ChartConfiguration } from 'chart.js';

interface DayStats {
  date: string;
  label: string;
  neg_hours: number;
  min_price: number;
  avg_price: number;
  wind_mw: number;
  solar_mw: number;
  gas_mw: number;
  total_mw: number;
  radiation_jcm2: number;
  sunshine_hours: number;
  wind_ms: number;
  hourly_prices: { hour: number; price: number }[];
}

interface KeyFactor {
  factor: string;
  extreme: number;
  reference: number;
  unit: string;
  change_pct: number;
}

interface AprilMay2026Data {
  extreme_days: DayStats[];
  reference_days: DayStats[];
  key_factors: KeyFactor[];
  summary: {
    worst_price: number;
    worst_date: string;
    total_extreme_neg_hours: number;
  };
}

export async function initAprilMay2026Charts(): Promise<AprilMay2026Data | null> {
  try {
    const response = await fetch('/data/april_may_2026.json');
    if (!response.ok) return null;
    const data: AprilMay2026Data = await response.json();

    updateStats(data);
    createFactorsChart(data.key_factors);
    createHourlyPriceChart(data.extreme_days, data.reference_days);

    return data;
  } catch (e) {
    console.error('Error loading april/may 2026 data:', e);
    return null;
  }
}

function updateStats(data: AprilMay2026Data) {
  const worstEl = document.getElementById('stat-am26-worst');
  const negEl = document.getElementById('stat-am26-neg-hours');
  const windEl = document.getElementById('stat-am26-wind');

  if (worstEl) worstEl.textContent = `€${data.summary.worst_price.toFixed(0)}/MWh`;
  if (negEl) negEl.textContent = `${data.summary.total_extreme_neg_hours}`;

  const may1 = data.extreme_days.find(d => d.date === '2026-05-01');
  const may1ref = data.reference_days.find(d => d.date === '2025-05-01');
  if (windEl && may1 && may1ref) {
    const ratio = Math.round(may1.wind_mw / may1ref.wind_mw * 10) / 10;
    windEl.textContent = `${ratio}×`;
  }
}

function createFactorsChart(factors: KeyFactor[]) {
  const canvas = document.getElementById('chart-am26-factors') as HTMLCanvasElement;
  if (!canvas) return;

  // Only show MW-based factors for the bar chart
  const mwFactors = factors.filter(f => f.unit === 'MW');

  const config: ChartConfiguration<'bar'> = {
    type: 'bar',
    data: {
      labels: mwFactors.map(f => f.factor),
      datasets: [
        {
          label: 'Extreme dagen 2026',
          data: mwFactors.map(f => f.extreme),
          backgroundColor: 'rgba(231, 76, 60, 0.75)',
          borderColor: 'rgb(231, 76, 60)',
          borderWidth: 1,
        },
        {
          label: 'Vergelijkbare dagen 2025',
          data: mwFactors.map(f => f.reference),
          backgroundColor: 'rgba(52, 152, 219, 0.7)',
          borderColor: 'rgb(52, 152, 219)',
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            label: (item) => {
              const f = mwFactors[item.dataIndex];
              const sign = f.change_pct > 0 ? '+' : '';
              return [
                `${item.dataset.label}: ${item.raw} ${f.unit}`,
                `Verschil: ${sign}${f.change_pct}%`,
              ];
            },
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          title: { display: true, text: 'Gemiddeld vermogen (MW)' },
        },
      },
    },
  };

  new Chart(canvas, config);
}

function createHourlyPriceChart(extremeDays: DayStats[], referenceDays: DayStats[]) {
  const canvas = document.getElementById('chart-am26-hourly') as HTMLCanvasElement;
  if (!canvas) return;

  const hours = Array.from({ length: 24 }, (_, i) => i);

  const getHourlyPrices = (day: DayStats) => {
    const map: Record<number, number> = {};
    day.hourly_prices.forEach(h => { map[h.hour] = h.price; });
    return hours.map(h => map[h] ?? null);
  };

  const colours = [
    { bg: 'rgba(231, 76, 60, 0.8)', border: 'rgb(231, 76, 60)' },
    { bg: 'rgba(230, 126, 34, 0.8)', border: 'rgb(230, 126, 34)' },
    { bg: 'rgba(155, 89, 182, 0.8)', border: 'rgb(155, 89, 182)' },
  ];
  const refColours = [
    { bg: 'rgba(52, 152, 219, 0.6)', border: 'rgb(52, 152, 219)' },
    { bg: 'rgba(26, 188, 156, 0.6)', border: 'rgb(26, 188, 156)' },
  ];

  const datasets = [
    ...extremeDays.map((day, i) => ({
      label: day.label,
      data: getHourlyPrices(day),
      borderColor: colours[i].border,
      backgroundColor: colours[i].bg,
      borderWidth: 2,
      pointRadius: 3,
      tension: 0.3,
      fill: false,
    })),
    ...referenceDays.map((day, i) => ({
      label: day.label,
      data: getHourlyPrices(day),
      borderColor: refColours[i].border,
      backgroundColor: refColours[i].bg,
      borderWidth: 2,
      borderDash: [5, 4],
      pointRadius: 2,
      tension: 0.3,
      fill: false,
    })),
  ];

  const config: ChartConfiguration<'line'> = {
    type: 'line',
    data: { labels: hours.map(h => `${h}:00`), datasets: datasets as any },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            label: (item) => `${item.dataset.label}: €${(item.raw as number).toFixed(1)}/MWh`,
          },
        },
      },
      scales: {
        y: {
          title: { display: true, text: 'Prijs (€/MWh)' },
        },
        x: {
          title: { display: true, text: 'Uur (UTC)' },
        },
      },
    },
  };

  new Chart(canvas, config);
}
