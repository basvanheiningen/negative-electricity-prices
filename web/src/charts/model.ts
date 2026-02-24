import { Chart, ChartConfiguration } from 'chart.js';

interface FeatureImportance {
  feature: string;
  importance: number;
}

interface MonthlyComparison {
  month: string;
  month_label: string;
  actual: number;
  predicted: number;
  correct: number;
}

interface ModelData {
  model_info: {
    name: string;
    type: string;
    train_period: string;
    test_period: string;
    train_hours: number;
    test_hours: number;
    train_negative_pct: number;
    test_negative_pct: number;
  };
  metrics: {
    accuracy: number;
    precision: number;
    recall: number;
    f1: number;
  };
  confusion_matrix: {
    true_negatives: number;
    false_positives: number;
    false_negatives: number;
    true_positives: number;
  };
  feature_importance: FeatureImportance[];
  monthly_comparison: MonthlyComparison[];
}

export async function initModelCharts(): Promise<ModelData | null> {
  try {
    const response = await fetch('/data/model_results.json');
    if (!response.ok) return null;
    const data: ModelData = await response.json();

    updateModelStats(data);
    createFeatureImportanceChart(data.feature_importance);
    createMonthlyComparisonChart(data.monthly_comparison);

    return data;
  } catch (e) {
    console.error('Error loading model data:', e);
    return null;
  }
}

function updateModelStats(data: ModelData) {
  const accEl = document.getElementById('stat-model-accuracy');
  const precEl = document.getElementById('stat-model-precision');
  const recEl = document.getElementById('stat-model-recall');

  if (accEl) accEl.textContent = `${(data.metrics.accuracy * 100).toFixed(1)}%`;
  if (precEl) precEl.textContent = `${(data.metrics.precision * 100).toFixed(1)}%`;
  if (recEl) recEl.textContent = `${(data.metrics.recall * 100).toFixed(1)}%`;
}

function createFeatureImportanceChart(data: FeatureImportance[]) {
  const canvas = document.getElementById('chart-feature-importance') as HTMLCanvasElement;
  if (!canvas) return;

  // Sort by importance
  const sorted = [...data].sort((a, b) => b.importance - a.importance);

  const config: ChartConfiguration<'bar'> = {
    type: 'bar',
    data: {
      labels: sorted.map(d => d.feature),
      datasets: [{
        label: 'Importance',
        data: sorted.map(d => d.importance * 100),
        backgroundColor: sorted.map((_, i) =>
          i === 0 ? 'rgba(241, 196, 15, 0.8)' :
          i < 3 ? 'rgba(52, 152, 219, 0.7)' : 'rgba(149, 165, 166, 0.6)'
        ),
        borderColor: sorted.map((_, i) =>
          i === 0 ? 'rgb(241, 196, 15)' :
          i < 3 ? 'rgb(52, 152, 219)' : 'rgb(149, 165, 166)'
        ),
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (item) => `${item.raw}%`
          }
        }
      },
      scales: {
        x: {
          beginAtZero: true,
          max: 50,
          title: { display: true, text: 'Belang (%)' }
        }
      }
    }
  };

  new Chart(canvas, config);
}

function createMonthlyComparisonChart(data: MonthlyComparison[]) {
  const canvas = document.getElementById('chart-monthly-model') as HTMLCanvasElement;
  if (!canvas) return;

  const config: ChartConfiguration<'bar'> = {
    type: 'bar',
    data: {
      labels: data.map(d => d.month_label),
      datasets: [
        {
          label: 'Werkelijk',
          data: data.map(d => d.actual),
          backgroundColor: 'rgba(46, 204, 113, 0.7)',
          borderColor: 'rgb(46, 204, 113)',
          borderWidth: 1
        },
        {
          label: 'Voorspeld',
          data: data.map(d => d.predicted),
          backgroundColor: 'rgba(52, 152, 219, 0.7)',
          borderColor: 'rgb(52, 152, 219)',
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'top' },
        tooltip: {
          callbacks: {
            afterBody: (items) => {
              const idx = items[0].dataIndex;
              return `Correct voorspeld: ${data[idx].correct}`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Negatieve uren' }
        }
      }
    }
  };

  new Chart(canvas, config);
}
