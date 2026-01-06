// static/projets/js/serviceworker.js
const CACHE_NAME = 'goprojet-v1.0';
const OFFLINE_URL = '/offline/';

// URLs à mettre en cache immédiatement
const urlsToCache = [
    '/',
    OFFLINE_URL,
    '/static/projets/css/style.css',
    '/static/projets/js/main.js',
    '/manifest.json',
    // Ajoutez autres ressources importantes ici
];

self.addEventListener('install', event => {
    console.log('[Service Worker] Installation');
    
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[Service Worker] Mise en cache des ressources initiales');
                return cache.addAll(urlsToCache);
            })
            .then(() => {
                console.log('[Service Worker] Installation terminée');
                return self.skipWaiting();
            })
    );
});

self.addEventListener('activate', event => {
    console.log('[Service Worker] Activation');
    
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[Service Worker] Suppression ancien cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
        .then(() => {
            console.log('[Service Worker] Prêt à gérer les requêtes');
            return self.clients.claim();
        })
    );
});

self.addEventListener('fetch', event => {
    // Ignorer les requêtes non-GET
    if (event.request.method !== 'GET') {
        return;
    }

    // Ignorer certaines URLs (admin, API)
    const url = new URL(event.request.url);
    if (url.pathname.startsWith('/admin/') || 
        url.pathname.startsWith('/api/')) {
        return;
    }

    event.respondWith(
        caches.match(event.request)
            .then(cachedResponse => {
                // Si en cache, retourner
                if (cachedResponse) {
                    console.log('[Service Worker] Ressource depuis cache:', url.pathname);
                    return cachedResponse;
                }

                // Sinon, réseau
                return fetch(event.request)
                    .then(response => {
                        // Vérifier si la réponse est valide
                        if (!response || response.status !== 200) {
                            return response;
                        }

                        // Mettre en cache pour la prochaine fois
                        const responseToCache = response.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => {
                                cache.put(event.request, responseToCache);
                            });

                        return response;
                    })
                    .catch(error => {
                        console.log('[Service Worker] Hors ligne, fallback:', error);
                        
                        // Pour les pages HTML
                        if (event.request.headers.get('accept').includes('text/html')) {
                            return caches.match(OFFLINE_URL);
                        }
                        
                        return new Response('', {
                            status: 408,
                            statusText: 'Hors ligne'
                        });
                    });
            })
    );
});