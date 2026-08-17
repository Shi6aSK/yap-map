"""
Eager model loading and management.
Models are loaded during backend startup so they're ready for live transcription.
"""
import asyncio
import logging
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ModelStatus(Enum):
    """Status of model initialization."""
    NOT_STARTED = "not_started"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


class ModelManager:
    """Manages eager model loading at startup."""
    
    def __init__(self):
        self.status = ModelStatus.NOT_STARTED
        self.error_message: Optional[str] = None
        self.vosk_transcriber = None
        self.local_model_manager = None
        self.topic_manager = None
        self.question_generator = None
    
    async def initialize_models(self):
        """Load all models in background during startup."""
        self.status = ModelStatus.LOADING
        print(">>> [MODEL INIT] Starting model initialization...")
        logger.info('Starting model initialization')
        
        try:
            # Load Vosk transcriber
            print(">>> [MODEL INIT] Loading Vosk transcriber...")
            await asyncio.get_event_loop().run_in_executor(None, self._load_vosk)
            
            # Load local models for embeddings and generation
            print(">>> [MODEL INIT] Loading local model manager...")
            await asyncio.get_event_loop().run_in_executor(None, self._load_local_models)
            
            # Load topic manager (uses sentence transformer)
            print(">>> [MODEL INIT] Loading topic manager...")
            from app.services.topic_manager import TopicManager
            self.topic_manager = TopicManager(model_manager=self.local_model_manager)
            
            # Load question generator (uses t5)
            print(">>> [MODEL INIT] Loading question generator...")
            from app.services.question_generator import QuestionGenerator
            self.question_generator = QuestionGenerator(model_manager=self.local_model_manager)
            
            self.status = ModelStatus.READY
            print(">>> [MODEL INIT] All models loaded successfully!")
            logger.info('All models initialized successfully')
            
        except Exception as exc:
            self.status = ModelStatus.FAILED
            self.error_message = str(exc)
            print(f">>> [MODEL INIT] ERROR: {exc}")
            logger.error('Model initialization failed: %s', exc, exc_info=True)
    
    def _load_vosk(self):
        """Load Vosk model (runs in executor)."""
        try:
            from app.services.transcription.vosk_transcriber import VoskTranscriber
            from app.services.local_models import LocalModelManager
            
            mm = LocalModelManager()
            vosk_path = mm.manifest.get('vosk_model')
            
            if vosk_path:
                print(f">>> [MODEL INIT] Loading Vosk from {vosk_path}")
                self.vosk_transcriber = VoskTranscriber(model_path=vosk_path)
                # Actually load the model (this is what takes time)
                print(f">>> [MODEL INIT] Initializing Vosk model...")
                self.vosk_transcriber._load_model()
                print(f">>> [MODEL INIT] Vosk model fully loaded")
                logger.info('Vosk model loaded: %s', vosk_path)
            else:
                logger.warning('Vosk model path not found')
        except Exception as exc:
            logger.error('Failed to load Vosk: %s', exc, exc_info=True)
            raise
    
    def _load_local_models(self):
        """Load local models (sentence transformers, t5) - runs in executor."""
        try:
            from app.services.local_models import LocalModelManager
            
            print(">>> [MODEL INIT] Creating LocalModelManager...")
            self.local_model_manager = LocalModelManager()
            
            # Force load embedding model
            print(">>> [MODEL INIT] Loading sentence-transformers embedding model...")
            self.local_model_manager.load_embedding()
            print(">>> [MODEL INIT] Embedding model loaded")
            
            # Force load generator pipeline
            print(">>> [MODEL INIT] Loading t5 generator pipeline...")
            self.local_model_manager.load_generator_pipeline()
            print(">>> [MODEL INIT] Generator pipeline loaded")
            
            logger.info('LocalModelManager initialized with all models loaded')
        except Exception as exc:
            logger.error('Failed to load local models: %s', exc, exc_info=True)
            raise
    
    def is_ready(self) -> bool:
        """Check if all models are ready."""
        return self.status == ModelStatus.READY


# Global model manager instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get the global model manager instance."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


async def initialize_models_on_startup():
    """Call this during app startup to load models in background."""
    manager = get_model_manager()
    await manager.initialize_models()
