import { Chart, ChartConfiguration } from 'chart.js';

interface YearlyEntry {
  year: number;
  count: number;
  extrapolated: boolean;
  extrapolated_count?: number;
  coverage?: number;
}

interface MonthlyComparisonData {
  years: number[];
  data: { year: number; month: number; count: number }[];
}

interface NegativePriceData {
  monthly: { month: string; count: number }[];
  monthly_comparison: MonthlyComparisonData;
  yearly: YearlyEntry[];
  heatmap: { hour: number; month: number; frequency: number }[];
  statistics: {
    total_hours: number;
    negative_hours: number;
    percentage: number;
    most_negative: { price: number; datetime: string };
    price_distribution: {
      min: number;
      max: number;
      mean: number;
      median: number;
    };
    date_range: { start: string; end: string };
  };
}

export async function initNegativePriceCharts(): Promise<NegativePriceData> {
  const response = await fetch('/data/negative_prices.json');
  const data: NegativePriceData = await response.json();

  // Update statistics
  updateStats(data.statistics);

  // Create charts
  createMonthlyComparisonChart(data.monthly_comparison);
  createYearlyChart(data.yearly);

  return data;
}

function updateStats(stats: NegativePriceData['statistics']) {
  const totalEl = document.getElementById('stat-total-hours');
  const percentageEl = document.getElementById('stat-percentage');
  const mostNegativeEl = document.getElementById('stat-most-negative');
  const dataPeriodEl = document.getElementById('data-period');

  if (totalEl) totalEl.textContent = stats.negative_hours.toLocaleString('nl-NL');
  if (percentageEl) percentageEl.textContent = `${stats.percentage}%`;
  if (mostNegativeEl) mostNegativeEl.textContent = `€${stats.most_negative.price}`;

  if (dataPeriodEl) {
    const start = new Date(stats.date_range.start).toLocaleDateString('nl-NL', {
      year: 'numeric',
      month: 'long'
    });
    const end = new Date(stats.date_range.end).toLocaleDateString('nl-NL', {
      year: 'numeric',
      month: 'long'
    });
    dataPeriodEl.textContent = `${start} - ${end}`;
  }
}

function createMonthlyComparisonChart(data: MonthlyComparisonData) {
  const canvas = document.getElementById('chart-monthly') as HTMLCanvasElement;
  if (!canvas) return;

  const monthNames = ['Jan', 'Feb', 'Mrt', 'Apr', 'Mei', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec'];

  // Colors for each year
  const yearColors: Record<number, { bg: string; border: string }> = {
    2024: { bg: 'rgba(52, 152, 219, 0.7)', border: 'rgb(52, 152, 219)' },
    2025: { bg: 'rgba(231, 76, 60, 0.7)', border: 'rgb(231, 76, 60)' },
    2026: { bg: 'rgba(46, 204, 113, 0.7)', border: 'rgb(46, 204, 113)' }
  };

  // Create datasets for each year
  const datasets = data.years.map(year => {
    const yearData = data.data.filter(d => d.year === year);
    const monthlyValues: (number | null)[] = [];

    for (let month = 1; month <= 12; month++) {
      const entry = yearData.find(d => d.month === month);
      monthlyValues.push(entry ? entry.count : null);
    }

    return {
      label: year.toString(),
      data: monthlyValues,
      backgroundColor: yearColors[year]?.bg || 'rgba(149, 165, 166, 0.7)',
      borderColor: yearColors[year]?.border || 'rgb(149, 165, 166)',
      borderWidth: 1
    };
  });

  const config: ChartConfiguration<'bar'> = {
    type: 'bar',
    data: {
      labels: monthNames,
      datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: 'top'
        },
        tooltip: {
          callbacks: {
            label: (item) => `${item.dataset.label}: ${item.raw} uren`
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Aantal uren' }
        },
        x: {
          title: { display: true, text: 'Maand' }
        }
      }
    }
  };

  new Chart(canvas, config);
}

function createYearlyChart(data: YearlyEntry[]) {
  const canvas = document.getElementById('chart-yearly') as HTMLCanvasElement;
  if (!canvas) return;

  // Find the extrapolated year
  const extrapolatedEntry = data.find(d => d.extrapolated);

  // Actual data: all points, but null for the extrapolated year's extrapolated value
  const actualData = data.map(d => d.count);

  // Create datasets
  const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
    {
      label: 'Negatieve uren per jaar',
      data: actualData,
      borderColor: 'rgb(231, 76, 60)',
      backgroundColor: 'rgba(231, 76, 60, 0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 6,
      pointHoverRadius: 8
    }
  ];

  // If there's an extrapolated year, add a second dataset for the dotted line
  if (extrapolatedEntry && extrapolatedEntry.extrapolated_count) {
    const extrapolatedIndex = data.findIndex(d => d.extrapolated);

    // Create data array with nulls except for the connection point and extrapolated point
    const extrapolatedData: (number | null)[] = data.map(() => null);

    // Connect from the last actual point of the extrapolated year to the extrapolated value
    if (extrapolatedIndex > 0) {
      extrapolatedData[extrapolatedIndex - 1] = data[extrapolatedIndex - 1].count;
    }
    extrapolatedData[extrapolatedIndex] = extrapolatedEntry.extrapolated_count;

    datasets.push({
      label: 'Extrapolatie',
      data: extrapolatedData,
      borderColor: 'rgb(231, 76, 60)',
      backgroundColor: 'transparent',
      borderDash: [5, 5],
      fill: false,
      tension: 0.3,
      pointRadius: 6,
      pointHoverRadius: 8,
      pointStyle: 'circle',
      pointBackgroundColor: 'white',
      pointBorderColor: 'rgb(231, 76, 60)',
      pointBorderWidth: 2
    });
  }

  const config: ChartConfiguration<'line'> = {
    type: 'line',
    data: {
      labels: data.map(d => d.year.toString()),
      datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: !!extrapolatedEntry,
          labels: {
            usePointStyle: true
          }
        },
        tooltip: {
          callbacks: {
            label: (item) => {
              const entry = data[item.dataIndex];
              if (item.datasetIndex === 1 && entry.extrapolated) {
                return `~${item.raw} uren (verwacht o.b.v. trend)`;
              }
              if (entry.extrapolated) {
                return `${item.raw} uren tot nu toe (${entry.coverage}% van jaar)`;
              }
              return `${item.raw} uren`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Aantal uren' }
        }
      }
    }
  };

  new Chart(canvas, config);
}
