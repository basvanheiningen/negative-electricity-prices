import { Chart, ChartConfiguration } from 'chart.js';

interface CorrelationData {
  overall_correlation: number;
  scatter: { solar: number; price: number; hour: number }[];
  hourly_correlation: { hour: number; correlation: number }[];
  season_correlation: Record<string, number>;
  weekend_correlation: { weekdag: number; weekend: number };
  timeseries: { datetime_utc: string; price_eur_mwh: number; solar_generation_mw: number }[];
  statistics: {
    n_observations: number;
    solar_range: { min: number; max: number; mean: number };
    price_range: { min: number; max: number; mean: number };
  };
}

export async function initCorrelationCharts(): Promise<CorrelationData> {
  const response = await fetch('/data/correlation.json');
  const data: CorrelationData = await response.json();

  // Update correlation stat
  const corrValueEl = document.getElementById('correlation-value');
  if (corrValueEl) {
    corrValueEl.textContent = data.overall_correlation.toFixed(2);
  }

  // Create charts
  createScatterChart(data.scatter);
  createHourlyCorrelationChart(data.hourly_correlation);
  createTimeseriesChart(data.timeseries);

  // Populate tables
  populateSeasonTable(data.season_correlation);
  populateWeekendTable(data.weekend_correlation);

  return data;
}

function createScatterChart(data: CorrelationData['scatter']) {
  const canvas = document.getElementById('chart-scatter') as HTMLCanvasElement;
  if (!canvas) return;

  // Color points by hour (solar hours get different color)
  const colors = data.map(d => {
    if (d.hour >= 10 && d.hour <= 16) {
      return 'rgba(243, 156, 18, 0.6)'; // Midday - orange
    }
    return 'rgba(52, 152, 219, 0.4)'; // Other hours - blue
  });

  const config: ChartConfiguration<'scatter'> = {
    type: 'scatter',
    data: {
      datasets: [{
        label: 'Prijs vs. Zonneproductie',
        data: data.map(d => ({ x: d.solar, y: d.price })),
        backgroundColor: colors,
        pointRadius: 3,
        pointHoverRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const raw = ctx.raw as { x: number; y: number };
              return `Zon: ${raw.x.toFixed(0)} MW, Prijs: €${raw.y.toFixed(2)}`;
            }
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: 'Zonne-energie (MW)' }
        },
        y: {
          title: { display: true, text: 'Prijs (€/MWh)' }
        }
      }
    }
  };

  new Chart(canvas, config);
}

function createHourlyCorrelationChart(data: CorrelationData['hourly_correlation']) {
  const canvas = document.getElementById('chart-hourly-corr') as HTMLCanvasElement;
  if (!canvas) return;

  // Color bars based on correlation strength
  const colors = data.map(d => {
    if (d.correlation < -0.3) return 'rgba(231, 76, 60, 0.7)';
    if (d.correlation < 0) return 'rgba(231, 76, 60, 0.4)';
    return 'rgba(39, 174, 96, 0.6)';
  });

  const config: ChartConfiguration<'bar'> = {
    type: 'bar',
    data: {
      labels: data.map(d => `${d.hour}:00`),
      datasets: [{
        label: 'Correlatie',
        data: data.map(d => d.correlation),
        backgroundColor: colors,
        borderColor: colors.map(c => c.replace('0.7', '1').replace('0.4', '0.8').replace('0.6', '1')),
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `Correlatie: ${(ctx.raw as number).toFixed(3)}`
          }
        }
      },
      scales: {
        y: {
          min: -1,
          max: 1,
          title: { display: true, text: 'Correlatie' },
          grid: {
            color: (ctx) => ctx.tick.value === 0 ? 'rgba(0,0,0,0.3)' : 'rgba(0,0,0,0.1)'
          }
        },
        x: {
          title: { display: true, text: 'Uur' },
          ticks: {
            callback: function(_, index) {
              return index % 4 === 0 ? data[index].hour + ':00' : '';
            }
          }
        }
      }
    }
  };

  new Chart(canvas, config);
}

function createTimeseriesChart(data: CorrelationData['timeseries']) {
  const canvas = document.getElementById('chart-timeseries') as HTMLCanvasElement;
  if (!canvas) return;

  const config: ChartConfiguration<'line'> = {
    type: 'line',
    data: {
      labels: data.map(d => {
        const date = new Date(d.datetime_utc);
        return date.toLocaleDateString('nl-NL', { month: 'short', year: '2-digit' });
      }),
      datasets: [
        {
          label: 'Prijs (€/MWh)',
          data: data.map(d => d.price_eur_mwh),
          borderColor: 'rgb(231, 76, 60)',
          backgroundColor: 'rgba(231, 76, 60, 0.1)',
          yAxisID: 'y',
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2
        },
        {
          label: 'Zonne-energie (MW)',
          data: data.map(d => d.solar_generation_mw),
          borderColor: 'rgb(243, 156, 18)',
          backgroundColor: 'rgba(243, 156, 18, 0.1)',
          yAxisID: 'y1',
          tension: 0.3,
          pointRadius: 0,
          borderWidth: 2
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
            label: (ctx) => {
              const value = ctx.raw as number;
              if (ctx.datasetIndex === 0) {
                return `Prijs: €${value.toFixed(2)}/MWh`;
              }
              return `Zon: ${value.toFixed(0)} MW`;
            }
          }
        }
      },
      scales: {
        y: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: 'Prijs (€/MWh)', color: 'rgb(231, 76, 60)' },
          ticks: { color: 'rgb(231, 76, 60)' }
        },
        y1: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: 'Zonne-energie (MW)', color: 'rgb(243, 156, 18)' },
          ticks: { color: 'rgb(243, 156, 18)' },
          grid: { drawOnChartArea: false }
        },
        x: {
          ticks: {
            maxTicksLimit: 12
          }
        }
      }
    }
  };

  new Chart(canvas, config);
}

function populateSeasonTable(data: Record<string, number>) {
  const tbody = document.querySelector('#table-season tbody');
  if (!tbody) return;

  const seasonNames: Record<string, string> = {
    'winter': 'Winter',
    'lente': 'Lente',
    'zomer': 'Zomer',
    'herfst': 'Herfst'
  };

  const order = ['lente', 'zomer', 'herfst', 'winter'];

  tbody.innerHTML = order.map(season => {
    const corr = data[season] ?? 0;
    const color = corr < -0.3 ? 'color: #e74c3c' : corr < 0 ? 'color: #e67e22' : 'color: #27ae60';
    return `<tr>
      <td>${seasonNames[season]}</td>
      <td style="${color}">${corr.toFixed(3)}</td>
    </tr>`;
  }).join('');
}

function populateWeekendTable(data: { weekdag: number; weekend: number }) {
  const tbody = document.querySelector('#table-weekend tbody');
  if (!tbody) return;

  tbody.innerHTML = `
    <tr>
      <td>Weekdag</td>
      <td style="color: #e74c3c">${data.weekdag.toFixed(3)}</td>
    </tr>
    <tr>
      <td>Weekend</td>
      <td style="color: #e74c3c">${data.weekend.toFixed(3)}</td>
    </tr>
  `;
}
