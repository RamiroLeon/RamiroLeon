import { useState } from 'react';
import './App.css';

function App() {
  const [theme, setTheme] = useState('');
  const [story, setStory] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isCreatingBook, setIsCreatingBook] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setStory(null);

    try {
      const response = await fetch('http://localhost:8000/api/generate-story', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to generate story');
      }

      const rawJsonString = await response.json();
      const storyData = JSON.parse(rawJsonString);
      setStory(storyData);

    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBook = async () => {
    if (!story) return;
    setIsCreatingBook(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/api/generate-book', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: story.title, paragraphs: story.paragraphs }),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to create book');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'libro_de_cuentos.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

    } catch (err) {
      setError(err.message);
    } finally {
      setIsCreatingBook(false);
    }
  };

  const handleReset = () => {
    setTheme('');
    setStory(null);
    setError(null);
  };

  return (
    <div className="container">
      <h1>La Fábrica de Cuentos</h1>

      {!story && (
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="theme">Escribe un tema para tu cuento:</label>
            <input
              id="theme"
              type="text"
              value={theme}
              onChange={(e) => setTheme(e.target.value)}
              placeholder="Ej: una aventura en el bosque"
              required
            />
          </div>
          <button type="submit" disabled={loading}>
            {loading ? 'Generando historia...' : 'Crear Historia'}
          </button>
        </form>
      )}

      {loading && <p>Creando un cuento mágico...</p>}

      {story && !isCreatingBook && (
        <div className="story-container">
          <h2>{story.title}</h2>
          {story.paragraphs.map((p, index) => (
            <p key={index}>{p}</p>
          ))}
          <button onClick={handleReset}>Crear otro cuento</button>
          <button onClick={handleCreateBook} disabled={isCreatingBook} style={{ marginLeft: '10px' }}>
            Aprobar y Crear Libro
          </button>
        </div>
      )}

      {isCreatingBook && (
          <div className="loading-book">
            <p>Generando las ilustraciones y el libro PDF...</p>
            <p>Este proceso puede tardar uno o dos minutos. ¡Gracias por tu paciencia!</p>
          </div>
      )}

      {error && (
        <div className="error-container">
          <p className="error">Error: {error}</p>
          <button onClick={handleReset}>Intentar de nuevo</button>
        </div>
      )}

    </div>
  );
}

export default App;
