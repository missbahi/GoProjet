let appData = { formData: null, initialized: false };

async function submitTacheForm(event) {
    event.preventDefault();
    const form = event.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn.innerHTML;
    
    try {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> En cours...';
        
        const tacheId = document.getElementById('tacheId').value;
        const url = tacheId ? `/taches/${tacheId}/modifier/` : '/taches/nouvelle/';
        
        const formData = new FormData(form);
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': '{{ csrf_token }}'
            }
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.message || 'Erreur lors de la sauvegarde');
        }
        
        showAlert('success', data.message);
        closeTaskModal();
        
        // Attendre un court instant avant le rafraîchissement
        setTimeout(refreshTachesList, 300);
        
    } catch (error) {
        console.error('Error:', error);
        showAlert('error', error.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
}

async function refreshTachesList() {
    const container = document.getElementById('taches-container');
    if (!container) return;

    try {
        const response = await fetch(window.location.href, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!response.ok) return;
        
        const html = await response.text();
        const newContainer = new DOMParser()
            .parseFromString(html, 'text/html')
            .getElementById('taches-container');
        
        if (newContainer) {
            container.innerHTML = newContainer.innerHTML;
            initializeEventHandlers();
        }
    } catch (error) {
        console.error('Refresh failed:', error);
    }
}

function initializeEventHandlers() {
    // Réattacher les écouteurs d'événements
    document.getElementById('avancement')?.addEventListener('input', function() {
        document.getElementById('avancementLabel').textContent = this.value + '%';
    });
    
    // Réattacher les boutons de modification
    document.querySelectorAll('[onclick^="openTaskModal"]').forEach(button => {
        const match = button.getAttribute('onclick').match(/openTaskModal\((\d+)\)/);
        if (match) {
            const taskId = match[1];
            button.onclick = () => openTaskModal(taskId);
        }
    });
}

function showAlert(type,message){
    const alert = document.createElement('div');
    alert.className = `fixed top-4 right-4 p-4 rounded-md text-white ${type==='success'?'bg-green-500':'bg-red-500'}`;
    alert.textContent = message;
    document.body.appendChild(alert);
    setTimeout(()=>alert.remove(),3000);
}

function showFormErrors(errors){
    document.querySelectorAll('.error-message').forEach(el=>el.remove());
    for(const [field,messages] of Object.entries(errors)){
        const input = document.querySelector(`[name="${field}"]`);
        if(input){
            const error = document.createElement('p');
            error.className='error-message text-red-500 text-sm mt-1';
            error.textContent = messages.map(m=>m.message).join(', ');
            input.parentNode.appendChild(error);
        }
    }
}

async function deleteTask(taskId) {
    if (!confirm('Voulez-vous vraiment supprimer cette tâche ?')) {
        return;
    }

    try {
        const response = await fetch(`/taches/${taskId}/supprimer/`, {
            method: 'DELETE',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            credentials: 'include'
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Erreur lors de la suppression');
        }

        const data = await response.json();
        
        if (data.success) {
            showAlert('success', data.message || 'Tâche supprimée avec succès');
            refreshTachesList(); // Rafraîchit la liste
        } else {
            throw new Error(data.message || 'Erreur inconnue');
        }
    } catch (error) {
        console.error('Erreur suppression:', error);
        showAlert('error', `Échec suppression: ${error.message}`);
    }
}

// Fonction utilitaire pour récupérer le cookie CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}