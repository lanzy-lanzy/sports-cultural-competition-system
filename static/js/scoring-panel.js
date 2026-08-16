document.addEventListener('DOMContentLoaded', function() {
    const scoringForm = document.getElementById('scoringForm');
    const scoreInputs = document.querySelectorAll('.score-input');
    let autoSaveTimeout;

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Score input validation and real-time updates
    scoreInputs.forEach(input => {
        input.addEventListener('input', function() {
            const max = parseFloat(this.getAttribute('max'));
            const value = parseFloat(this.value);
            
            if (value > max) {
                this.value = max;
                showNotification('Score cannot exceed maximum value', 'warning');
            }
            
            updateTotalScore(this.closest('tr'));
            triggerAutoSave();
        });
    });

    // Auto-save functionality
    function triggerAutoSave() {
        clearTimeout(autoSaveTimeout);
        autoSaveTimeout = setTimeout(() => {
            saveScores('save');
        }, 2000);
    }

    // Save scores function
    function saveScores(action) {
        const formData = new FormData(scoringForm);
        formData.append('action', action);

        fetch(window.location.href, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showNotification(action === 'save' ? 'Scores saved successfully' : 'Scores submitted successfully', 'success');
                updateProgressCircle();
            }
        })
        .catch(error => {
            showNotification('Error saving scores', 'error');
        });
    }

    // Update total score calculation
    function updateTotalScore(row) {
        const inputs = row.querySelectorAll('.score-input');
        let total = 0;
        
        inputs.forEach(input => {
            total += parseFloat(input.value) || 0;
        });

        const totalCell = row.querySelector('.total-score');
        if (totalCell) {
            totalCell.textContent = total.toFixed(2);
        }
    }

    // Progress circle animation
    function updateProgressCircle() {
        const progressCircle = document.querySelector('.progress-circle');
        const percentage = calculateCompletionPercentage();
        progressCircle.style.setProperty('--progress', percentage);
        progressCircle.querySelector('.progress-text').textContent = `${percentage}%`;
    }

    // Calculate completion percentage
    function calculateCompletionPercentage() {
        const filledInputs = Array.from(scoreInputs).filter(input => input.value !== '').length;
        return Math.round((filledInputs / scoreInputs.length) * 100);
    }

    // Notification system
    function showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} notification`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        setTimeout(() => notification.remove(), 3000);
    }

    // Form submission handlers
    scoringForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const submitButton = e.submitter;
        saveScores(submitButton.value);
    });

    // Initialize scoring panel
    updateProgressCircle();
});
