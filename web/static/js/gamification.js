// Ocean-themed Gamification JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize progress bars with animation
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        const targetWidth = bar.getAttribute('aria-valuenow') + '%';
        bar.style.width = '0%';
        setTimeout(() => {
            bar.style.transition = 'width 1s ease-in-out';
            bar.style.width = targetWidth;
        }, 200);
    });
    
    // Leaderboard tabs
    const globalTab = document.getElementById('global-tab');
    const connectionsTab = document.getElementById('connections-tab');
    const globalLeaderboard = document.getElementById('global-leaderboard');
    const connectionsLeaderboard = document.getElementById('connections-leaderboard');
    
    if (globalTab && connectionsTab) {
        globalTab.addEventListener('click', function() {
            globalLeaderboard.classList.add('active');
            connectionsLeaderboard.classList.remove('active');
            globalTab.classList.add('active');
            connectionsTab.classList.remove('active');
        });
        
        connectionsTab.addEventListener('click', function() {
            connectionsLeaderboard.classList.add('active');
            globalLeaderboard.classList.remove('active');
            connectionsTab.classList.add('active');
            globalTab.classList.remove('active');
        });
    }
    
    // Challenge accept buttons
    const challengeButtons = document.querySelectorAll('.accept-challenge');
    challengeButtons.forEach(button => {
        button.addEventListener('click', function() {
            const challengeId = this.getAttribute('data-challenge-id');
            this.innerHTML = '<i class="fas fa-check"></i> Accepted';
            this.classList.remove('btn-primary');
            this.classList.add('btn-success');
            this.disabled = true;
            
            // In a real implementation, this would call an API to accept the challenge
            console.log('Challenge accepted:', challengeId);
        });
    });
    
    // Badge hover effects
    const badges = document.querySelectorAll('.badge-item');
    badges.forEach(badge => {
        badge.addEventListener('mouseenter', function() {
            this.querySelector('.badge-icon').classList.add('pulse');
        });
        
        badge.addEventListener('mouseleave', function() {
            this.querySelector('.badge-icon').classList.remove('pulse');
        });
    });
    
    // Animate researcher level on page load
    const levelElement = document.querySelector('.researcher-level h2');
    const rankElement = document.querySelector('.researcher-level h4');
    
    if (levelElement) {
        animateCounter(levelElement, 0, parseInt(levelElement.getAttribute('data-level')), 1500);
    }
    
    if (rankElement) {
        setTimeout(() => {
            rankElement.classList.add('fade-in');
        }, 500);
    }
    
    // Animate statistics on scroll
    const statItems = document.querySelectorAll('.stat-item h3');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const target = entry.target;
                const value = parseInt(target.getAttribute('data-value'));
                animateCounter(target, 0, value, 2000);
                observer.unobserve(target);
            }
        });
    }, { threshold: 0.5 });
    
    statItems.forEach(item => {
        observer.observe(item);
    });
    
    // Function to animate counting up
    function animateCounter(element, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const value = Math.floor(progress * (end - start) + start);
            element.innerText = value;
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }
    
    // Ocean-themed particle animation
    const particleContainer = document.querySelector('.particle-container');
    if (particleContainer) {
        for (let i = 0; i < 20; i++) {
            createParticle(particleContainer);
        }
    }
    
    function createParticle(container) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        
        // Random position, size, and animation duration
        const size = Math.random() * 10 + 5;
        const posX = Math.random() * 100;
        const posY = Math.random() * 100;
        const duration = Math.random() * 20 + 10;
        const delay = Math.random() * 5;
        
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        particle.style.left = `${posX}%`;
        particle.style.top = `${posY}%`;
        particle.style.animationDuration = `${duration}s`;
        particle.style.animationDelay = `${delay}s`;
        
        container.appendChild(particle);
    }
});