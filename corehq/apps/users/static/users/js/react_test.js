import React from 'react';
import { createRoot } from 'react-dom/client';

export default function ReactButton() {
    return (
        <h1>Hello World</h1>
    );
}

window.addEventListener('load', () => {
    const root = createRoot(document.getElementById('reactRoot'));
    root.render(<ReactButton/>);
});