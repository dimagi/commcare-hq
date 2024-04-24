import React from 'react';
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