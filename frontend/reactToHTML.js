import React from 'react';
import { createRoot } from 'react-dom/client';
import { useState, useEffect } from 'react';


export default function ReactToHTML({outputSpan}) {
    const [value, setValue] = useState('Hello World');
    useEffect(() => {
        outputSpan.innerHTML = value;
    }, [value]);

    return (
        <>
            <input type="text" value={value} onChange={e => setValue(e.target.value)}></input>
        </>
    );
}

window.addEventListener('load', () => {
    const outputSpan = document.getElementById('htmlSpan');
    const reactToHTMLRoot = createRoot(document.getElementById('reactToHTMLRoot'));
    reactToHTMLRoot.render(<ReactToHTML outputSpan={outputSpan} />);
});