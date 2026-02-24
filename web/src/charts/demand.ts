import { Chart, ChartConfiguration } from 'chart.js';

interface DayOfWeekData {
  day: string;
  day_num: number;
  negative_hours: number;
  total_hours: number;
  probability: number;
  avg_price: number;
  is_weekend: boolean;
}

interface HourlyComparison {
  hours: number[];
  weekday: {
    negative_probability: number[];
    avg_price: number[];
  };
  weekend: {
    negative_probability: number[];
    avg_price: number[];
  };
  holiday: {
    negative_probability: number[];
    avg_price: number[];
  };
}

interface DemandData {
  dayofweek: DayOfWeekData[];
  hourly_comparison: HourlyComparison;
  weekend_comparison: {
    weekday: { probability: number; avg_price: number };
    weekend: { probability: number; avg_price: number };
  };
  holiday_stats: {
    holiday: { probability: number };
    non_holiday: { probability: number };
  };
  statistics: {
    weekend_factor: number;
  };
}

export async function initDemandCharts(): Promise<DemandData | null> {
  try {
    const response = await fetch('/data/demand.json');
    if (!response.ok) return null;
    const data: DemandData = await response.json();

    // Update statistics
    updateDemandStats(data);

    // Create charts
    createDayOfWeekChart(data.dayofweek);
    createHourlyDemandChart(data.hourly_comparison);

    return data;
  } catch (e) {
    console.error('Error loading demand data:', e);
    return null;
  }
}

function updateDemandStats(data: DemandData) {
  const weekendFactorEl = document.getElementById('stat-weekend-factor');
  const sundayProbEl = document.getElementById('stat-sunday-prob');
  const holidayProbEl = document.getElementById('stat-holiday-prob');

  if (weekendFactorEl) weekendFactorEl.textContent = `${data.statistics.weekend_factor}`;

  const sunday = data.dayofweek.find(d => d.day_num === 6);
  if (sundayProbEl && sunday) sundayProbEl.textContent = `${sunday.probability}%`;

  if (holidayProbEl) holidayProbEl.textContent = `${data.holiday_stats.holiday.probability}%`;
}

function createDayOfWeekChart(data: DayOfWeekData[]) {
  const canvas = document.getElementById('chart-dayofweek') as HTMLCanvasElement;
  if (!canvas) return;

  const colors = data.map(d => d.is_weekend ? 'rgba(155, 89, 182, 0.7)' : 'rgba(52, 152, 219, 0.7)');
  const borderColors = data.map(d => d.is_weekend ? 'rgb(155, 89, 182)' : 'rgb(52, 152, 219)');

  const config: ChartConfiguration<'bar'> = {
    type: 'bar',
    data: {
      labels: data.map(d => d.day),
      datasets: [{
        label: 'Kans op negatieve prijs (%)',
        data: data.map(d => d.probability),
        backgroundColor: colors,
        borderColor: borderColors,
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
            label: (item) => {
              const d = data[item.dataIndex];
              return [
                `Kans: ${d.probability}%`,
                `${d.negative_hours} van ${d.total_hours} uren`
              ];
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Kans (%)' }
        }
      }
    }
  };

  new Chart(canvas, config);
}

function createHourlyDemandChart(data: HourlyComparison) {
  const canvas = document.getElementById('chart-hourly-demand') as HTMLCanvasElement;
  if (!canvas) return;

  const config: ChartConfiguration<'line'> = {
    type: 'line',
    data: {
      labels: data.hours.map(h => `${h}:00`),
      datasets: [
        {
          label: 'Weekdag',
          data: data.weekday.negative_probability,
          borderColor: 'rgb(52, 152, 219)',
          backgroundColor: 'rgba(52, 152, 219, 0.1)',
          fill: false,
          tension: 0.3,
          pointRadius: 2
        },
        {
          label: 'Weekend',
          data: data.weekend.negative_probability,
          borderColor: 'rgb(155, 89, 182)',
          backgroundColor: 'rgba(155, 89, 182, 0.1)',
          fill: false,
          tension: 0.3,
          pointRadius: 2
        },
        {
          label: 'Feestdag',
          data: data.holiday.negative_probability,
          borderColor: 'rgb(231, 76, 60)',
          backgroundColor: 'rgba(231, 76, 60, 0.1)',
          fill: false,
          tension: 0.3,
          pointRadius: 2
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
            label: (item) => `${item.dataset.label}: ${item.raw}%`
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Kans op negatieve prijs (%)' }
        },
        x: {
          title: { display: true, text: 'Uur' },
          ticks: {
            callback: function(_, index) {
              return index % 4 === 0 ? data.hours[index] + ':00' : '';
            }
          }
        }
      }
    }
  };

  new Chart(canvas, config);
}

