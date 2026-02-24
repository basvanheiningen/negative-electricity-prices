import { Chart, ChartConfiguration } from 'chart.js';

interface KeyDifference {
  factor: string;
  "2024": number;
  "2025": number;
  change_pct: number;
  unit: string;
}

interface JulyComparisonData {
  summary: {
    "2024": {
      negative_hours: number;
      total_hours: number;
      percentage: number;
      avg_price: number;
      min_price: number;
      avg_solar_mw: number;
      avg_wind_mw: number;
      avg_gas_mw: number;
      total_production_mw: number;
    };
    "2025": {
      negative_hours: number;
      total_hours: number;
      percentage: number;
      avg_price: number;
      min_price: number;
      avg_solar_mw: number;
      avg_wind_mw: number;
      avg_gas_mw: number;
      total_production_mw: number;
    };
  };
  key_differences: KeyDifference[];
}

export async function initJulyComparisonCharts(): Promise<JulyComparisonData | null> {
  try {
    const response = await fetch('/data/july_comparison.json');
    if (!response.ok) return null;
    const data: JulyComparisonData = await response.json();

    // Update statistics
    updateJulyStats(data);

    // Create charts
    createKeyFactorsChart(data.key_differences);

    return data;
  } catch (e) {
    console.error('Error loading July comparison data:', e);
    return null;
  }
}

function updateJulyStats(data: JulyComparisonData) {
  const neg2024El = document.getElementById('stat-neg-2024');
  const neg2025El = document.getElementById('stat-neg-2025');
  const ratioEl = document.getElementById('stat-neg-ratio');

  if (neg2024El) neg2024El.textContent = `${data.summary['2024'].negative_hours}`;
  if (neg2025El) neg2025El.textContent = `${data.summary['2025'].negative_hours}`;
  if (ratioEl) {
    const ratio = data.summary['2024'].negative_hours / data.summary['2025'].negative_hours;
    ratioEl.textContent = `${ratio.toFixed(1)}x`;
  }
}

function createKeyFactorsChart(data: KeyDifference[]) {
  const canvas = document.getElementById('chart-factors-july') as HTMLCanvasElement;
  if (!canvas) return;

  const config: ChartConfiguration<'bar'> = {
    type: 'bar',
    data: {
      labels: data.map(d => d.factor),
      datasets: [
        {
          label: 'Juli 2024',
          data: data.map(d => d['2024']),
          backgroundColor: 'rgba(231, 76, 60, 0.7)',
          borderColor: 'rgb(231, 76, 60)',
          borderWidth: 1
        },
        {
          label: 'Juli 2025',
          data: data.map(d => d['2025']),
          backgroundColor: 'rgba(52, 152, 219, 0.7)',
          borderColor: 'rgb(52, 152, 219)',
          borderWidth: 1
        }
      ]
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
              const d = data[item.dataIndex];
              const sign = d.change_pct > 0 ? '+' : '';
              return [
                `${item.dataset.label}: ${item.raw} ${d.unit}`,
                `Verschil: ${sign}${d.change_pct}%`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          beginAtZero: true,
          title: { display: true, text: 'Gemiddeld vermogen (MW)' }
        }
      }
    }
  };

  new Chart(canvas, config);
}
