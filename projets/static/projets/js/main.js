
//script pour la fermeture des messages

document.addEventListener('DOMContentLoaded', function() {
const messages = document.querySelectorAll('[class*="bg-green-100"]');
messages.forEach(message => {
    setTimeout(() => {
        message.style.transition = 'opacity 0.5s ease';
        message.style.opacity = '0';
        setTimeout(() => message.remove(), 500); // Suppression après l'animation
    }, 3000); // 2 secondes
});
}); 

// Auto-dismiss messages after 3 seconds 
function setupMessages() {
document.querySelectorAll('.django-message').forEach(msg => {
    // Auto-dismiss
    const timer = setTimeout(() => {
        msg.classList.add('message-fadeout');
        setTimeout(() => msg.remove(), 500);
    }, 3000);

    // Dismiss manuel
    msg.querySelector('.dismiss-btn').addEventListener('click', () => {
        clearTimeout(timer);
        msg.classList.add('message-fadeout');
        setTimeout(() => msg.remove(), 500);
    });
});
} 