import {
  Chart,
  CategoryScale,
  LinearScale,
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  ScatterController,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';

import { initNegativePriceCharts } from './charts/negativeprices';
import { initCorrelationCharts } from './charts/correlation';
import { initEnergyMixCharts } from './charts/energymix';
import { initDemandCharts } from './charts/demand';
import { initWeatherCharts } from './charts/weather';
import { initJulyComparisonCharts } from './charts/julycomparison';
import { initSeptemberComparisonCharts } from './charts/septembercomparison';
import { initModelCharts } from './charts/model';

// Register Chart.js components
Chart.register(
  CategoryScale,
  LinearScale,
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  ScatterController,
  Tooltip,
  Legend,
  Filler
);

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
  // Initialize charts
  try {
    await Promise.all([
      initNegativePriceCharts(),
      initEnergyMixCharts(),
      initWeatherCharts(),
      initDemandCharts(),
      initJulyComparisonCharts(),
      initSeptemberComparisonCharts(),
      initModelCharts(),
      initCorrelationCharts()
    ]);
    console.log('Charts initialized successfully');
  } catch (error) {
    console.error('Error initializing charts:', error);
  }

  // Initialize reason card interactions
  initReasonCards();

  // Initialize scroll navigation
  initScrollNavigation();
});

function initReasonCards() {
  const cards = document.querySelectorAll('.reason-card');

  cards.forEach(card => {
    card.addEventListener('click', () => {
      // Close other cards
      cards.forEach(c => {
        if (c !== card) c.classList.remove('expanded');
      });

      // Toggle current card
      card.classList.toggle('expanded');
    });
  });
}

function initScrollNavigation() {
  const container = document.querySelector('.scroll-container');
  const dots = document.querySelectorAll('.dot');
  const sections = document.querySelectorAll('.section');

  if (!container || !dots.length || !sections.length) return;

  // Update active dot on scroll
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const index = Array.from(sections).indexOf(entry.target as Element);
          dots.forEach((dot, i) => {
            dot.classList.toggle('active', i === index);
          });
        }
      });
    },
    {
      root: container,
      threshold: 0.5
    }
  );

  sections.forEach(section => observer.observe(section));

  // Click on dots to navigate
  dots.forEach((dot, index) => {
    dot.addEventListener('click', (e) => {
      e.preventDefault();
      sections[index].scrollIntoView({ behavior: 'smooth' });
    });
  });

  // Keyboard navigation
  document.addEventListener('keydown', (e) => {
    const currentIndex = Array.from(dots).findIndex(dot => dot.classList.contains('active'));

    if (e.key === 'ArrowDown' || e.key === 'PageDown') {
      e.preventDefault();
      const nextIndex = Math.min(currentIndex + 1, sections.length - 1);
      sections[nextIndex].scrollIntoView({ behavior: 'smooth' });
    } else if (e.key === 'ArrowUp' || e.key === 'PageUp') {
      e.preventDefault();
      const prevIndex = Math.max(currentIndex - 1, 0);
      sections[prevIndex].scrollIntoView({ behavior: 'smooth' });
    }
  });
}
