import React from 'react';
import { useState, useEffect } from 'react';

export default function ReadFromKnockout({inputSelector}) {
    let [value, setValue] = useState('');
    const inputHandler = (e) => setValue(e.target.value);

    useEffect(() => {
        const ele = document.querySelector(inputSelector);
        setValue(ele.value);

        ele.addEventListener('input', inputHandler);
        return () => ele.removeEventListener('input', inputHandler);
    }, [inputSelector]);

    return (
        <>
            <h1>Hello, {value}!</h1>
        </>
    );
}
