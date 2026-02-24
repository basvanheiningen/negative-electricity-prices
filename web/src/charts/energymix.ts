import { Chart, ChartConfiguration } from 'chart.js';

interface YearlyData {
  year: number;
  renewable_share: number;
  negative_hours: number;
  renewable_mw: number;
}

interface EnergyMixData {
  yearly: YearlyData[];
  correlation: number;
  statistics: {
    avg_renewable_share: number;
    max_renewable_share: number;
    date_range: { start: string; end: string };
  };
}

export async function initEnergyMixCharts(): Promise<EnergyMixData | null> {
  try {
    const response = await fetch('/data/energy_mix.json');
    if (!response.ok) return null;
    const data: EnergyMixData = await response.json();

    // Update statistics
    updateEnergyStats(data);

    // Create charts
    createYearlyRenewableChart(data.yearly);

    return data;
  } catch (e) {
    console.error('Error loading energy mix data:', e);
    return null;
  }
}

function updateEnergyStats(data: EnergyMixData) {
  const renewableEl = document.getElementById('stat-renewable-share');
  const correlationEl = document.getElementById('stat-correlation');

  if (renewableEl) renewableEl.textContent = `${data.statistics.avg_renewable_share}%`;
  if (correlationEl) correlationEl.textContent = data.correlation.toFixed(2);
}

function createYearlyRenewableChart(data: YearlyData[]) {
  const canvas = document.getElementById('chart-yearly-renewable') as HTMLCanvasElement;
  if (!canvas) return;

  const config: ChartConfiguration<'bar' | 'line'> = {
    type: 'bar',
    data: {
      labels: data.map(d => d.year.toString()),
      datasets: [
        {
          type: 'line',
          label: 'Aandeel hernieuwbaar (%)',
          data: data.map(d => d.renewable_share),
          borderColor: '#27ae60',
          backgroundColor: 'rgba(39, 174, 96, 0.1)',
          yAxisID: 'y',
          tension: 0.3,
          pointRadius: 6,
          pointHoverRadius: 8,
          fill: false,
          order: 1
        },
        {
          type: 'bar',
          label: 'Negatieve uren',
          data: data.map(d => d.negative_hours),
          backgroundColor: 'rgba(231, 76, 60, 0.7)',
          borderColor: 'rgb(231, 76, 60)',
          borderWidth: 1,
          yAxisID: 'y1',
          order: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top'
        },
        tooltip: {
          callbacks: {
            label: (item) => {
              if (item.datasetIndex === 0) {
                return `Hernieuwbaar: ${item.raw}%`;
              }
              return `Negatieve uren: ${item.raw}`;
            }
          }
        }
      },
      scales: {
        y: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: 'Aandeel hernieuwbaar (%)', color: '#27ae60' },
          ticks: { color: '#27ae60' },
          min: 0,
          max: 30
        },
        y1: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: 'Negatieve uren', color: '#e74c3c' },
          ticks: { color: '#e74c3c' },
          min: 0,
          grid: { drawOnChartArea: false }
        }
      }
    }
  };

  new Chart(canvas, config);
}

