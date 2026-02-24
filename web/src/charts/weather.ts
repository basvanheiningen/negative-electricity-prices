import { Chart, ChartConfiguration } from 'chart.js';

interface RadiationBucket {
  bucket: string;
  negative_hours: number;
  total_hours: number;
  probability: number;
  avg_solar_mw: number;
}

interface WindBucket {
  bucket: string;
  negative_hours: number;
  total_hours: number;
  probability: number;
  avg_wind_mw: number;
}

interface WeatherData {
  radiation_buckets: RadiationBucket[];
  wind_buckets: WindBucket[];
  correlations: {
    radiation_solar: number;
    wind_speed_wind: number;
    radiation_price: number;
    wind_speed_price: number;
  };
}

export async function initWeatherCharts(): Promise<WeatherData | null> {
  try {
    const response = await fetch('/data/weather.json');
    if (!response.ok) return null;
    const data: WeatherData = await response.json();

    // Update statistics
    updateWeatherStats(data);

    // Create charts
    createRadiationBucketsChart(data.radiation_buckets);
    createWindBucketsChart(data.wind_buckets);

    return data;
  } catch (e) {
    console.error('Error loading weather data:', e);
    return null;
  }
}

function updateWeatherStats(data: WeatherData) {
  const corrSolarEl = document.getElementById('stat-corr-solar');
  const corrWindEl = document.getElementById('stat-corr-wind');

  if (corrSolarEl) corrSolarEl.textContent = data.correlations.radiation_solar.toFixed(2);
  if (corrWindEl) corrWindEl.textContent = data.correlations.wind_speed_wind.toFixed(2);
}

function createRadiationBucketsChart(data: RadiationBucket[]) {
  const canvas = document.getElementById('chart-radiation-buckets') as HTMLCanvasElement;
  if (!canvas) return;

  const config: ChartConfiguration<'bar'> = {
    type: 'bar',
    data: {
      labels: data.map(d => d.bucket),
      datasets: [{
        label: 'Kans op negatieve prijs (%)',
        data: data.map(d => d.probability),
        backgroundColor: 'rgba(241, 196, 15, 0.7)',
        borderColor: 'rgb(241, 196, 15)',
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
                `${d.negative_hours} van ${d.total_hours} uren`,
                `Gem. productie: ${d.avg_solar_mw} MW`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: 'Globale straling (J/cm²)' }
        },
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Kans (%)' }
        }
      }
    }
  };

  new Chart(canvas, config);
}

function createWindBucketsChart(data: WindBucket[]) {
  const canvas = document.getElementById('chart-wind-buckets') as HTMLCanvasElement;
  if (!canvas) return;

  const config: ChartConfiguration<'bar'> = {
    type: 'bar',
    data: {
      labels: data.map(d => d.bucket),
      datasets: [{
        label: 'Kans op negatieve prijs (%)',
        data: data.map(d => d.probability),
        backgroundColor: 'rgba(52, 152, 219, 0.7)',
        borderColor: 'rgb(52, 152, 219)',
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
                `${d.negative_hours} van ${d.total_hours} uren`,
                `Gem. productie: ${d.avg_wind_mw} MW`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: 'Windsnelheid (m/s)' }
        },
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Kans (%)' }
        }
      }
    }
  };

  new Chart(canvas, config);
}
