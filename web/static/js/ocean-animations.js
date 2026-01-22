/**
 * DeepSea eDNA Explorer - Ocean Animations
 * Enhances the ocean theme with dynamic animations
 */

document.addEventListener('DOMContentLoaded', function() {
    // Add random movement to bubbles
    const bubbles = document.querySelectorAll('.bubble');
    
    bubbles.forEach(bubble => {
        // Random horizontal position
        const randomLeft = Math.floor(Math.random() * 90) + 5; // 5% to 95%
        bubble.style.left = `${randomLeft}%`;
        
        // Random animation duration
        const randomDuration = Math.floor(Math.random() * 5) + 8; // 8s to 13s
        bubble.style.animationDuration = `${randomDuration}s`;
        
        // Random animation delay
        const randomDelay = Math.floor(Math.random() * 5);
        bubble.style.animationDelay = `${randomDelay}s`;
        
        // Random size
        const randomSize = Math.floor(Math.random() * 40) + 20; // 20px to 60px
        bubble.style.width = `${randomSize}px`;
        bubble.style.height = `${randomSize}px`;
    });
    
    // Add parallax effect to ocean waves
    window.addEventListener('mousemove', function(e) {
        const moveX = (e.clientX / window.innerWidth) * 10;
        const moveY = (e.clientY / window.innerHeight) * 5;
        
        const waves = document.querySelectorAll('.wave-top, .wave-middle, .wave-bottom');
        waves.forEach((wave, index) => {
            const factor = (index + 1) * 0.5;
            wave.style.transform = `translate(${moveX * factor}px, ${moveY * factor}px)`;
        });
    });
    
    // Add subtle pulse animation to login/signup cards
    const loginCards = document.querySelectorAll('.login-card');
    loginCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            card.classList.add('card-pulse');
        });
        
        card.addEventListener('mouseleave', function() {
            card.classList.remove('card-pulse');
        });
    });
    
    // Add CSS for the pulse animation if it doesn't exist
    if (!document.getElementById('pulse-animation-style')) {
        const style = document.createElement('style');
        style.id = 'pulse-animation-style';
        style.textContent = `
            @keyframes card-pulse {
                0% { box-shadow: 0 10px 30px rgba(0, 105, 192, 0.2); }
                50% { box-shadow: 0 15px 40px rgba(0, 105, 192, 0.4); }
                100% { box-shadow: 0 10px 30px rgba(0, 105, 192, 0.2); }
            }
            
            .card-pulse {
                animation: card-pulse 2s infinite ease-in-out;
            }
        `;
        document.head.appendChild(style);
    }
});