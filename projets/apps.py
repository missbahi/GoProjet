from django.apps import AppConfig


class ProjetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'projets'
    
    def ready(self):
        """ Charge tous les signaux quand l'app est prête."""
        # Éviter le double chargement (important pour les tests)
        if not hasattr(self, 'signals_loaded'):
            # Import des signaux
            try:
                import projets.signals
                print(f"✅ Tous les signaux chargés pour {self.name}")
                
                # OU import spécifique
                # import projets.signals.notifications
                # import projets.signals.file_handler
                
            except ImportError as e:
                print(f"❌ Erreur lors du chargement des signaux: {e}")
                import traceback
                traceback.print_exc()
            
            self.signals_loaded = True
