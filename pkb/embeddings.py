from typing import List, Optional

import numpy as np


class EmbeddingGenerator:
    """
    Wrapper for generating embeddings using sentence-transformers.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None,
    ):
        """
        Initialize embedding generator.

        Args:
            model_name: Name of the sentence-transformers model to use
        """
        self.model_name = model_name
        self._model = None
        self.device = device

    def _load_model(self):
        """
        Lazy load the model on first use.
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for embeddings. "
                    "Install with: pip install sentence-transformers"
                )

            print(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name, device=self.device)

    def encode(
        self, texts: List[str], batch_size: int = 32, show_progress: bool = False
    ) -> np.ndarray:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar

        Returns:
            Numpy array of embeddings (shape: [len(texts), embedding_dim])
        """
        if not texts:
            return np.array([])

        self._load_model()

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )

        return embeddings

    def encode_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding as list of floats
        """
        embeddings = self.encode([text])
        return embeddings[0].tolist()

    def get_embedding_dim(self) -> int:
        """
        Get the embedding dimension for this model.

        Returns:
            Embedding dimension
        """
        self._load_model()
        return self._model.get_sentence_embedding_dimension()

    def __repr__(self) -> str:
        return f"EmbeddingGenerator(model={self.model_name})"
