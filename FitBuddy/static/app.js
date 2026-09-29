/**
 * FitBuddy – Client-side script for FastAPI + Jinja2 frontend
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initial Plan Generation Form Handler
  const planForm = document.getElementById('planForm');
  const generateBtn = document.getElementById('generateBtn');
  const loadingIndicator = document.getElementById('loadingIndicator');

  if (planForm && generateBtn && loadingIndicator) {
    planForm.addEventListener('submit', () => {
      generateBtn.style.display = 'none';
      loadingIndicator.style.display = 'flex';
    });
  }

  // 2. Adaptive Plan Feedback Form Handler
  const feedbackForm = document.getElementById('feedbackForm');
  const submitFeedbackBtn = document.getElementById('submitFeedbackBtn');
  const feedbackLoadingIndicator = document.getElementById('feedbackLoadingIndicator');

  if (feedbackForm && submitFeedbackBtn && feedbackLoadingIndicator) {
    feedbackForm.addEventListener('submit', () => {
      submitFeedbackBtn.disabled = true;
      submitFeedbackBtn.style.opacity = '0.6';
      feedbackLoadingIndicator.style.display = 'flex';
    });
  }
});
