import React from 'react';
import { createRoot } from 'react-dom/client';

import ModalPopup from './modalPopup';
import ReadFromKnockout from './readFromKnockout';
import ReactToHTML from './reactToHTML';
import LocalTable from './localTable';
import RemoteTable from './remoteTable';
import ButtonTable from './buttonTable';

window.addEventListener('load', () => {
    const formHTML = document.querySelector('#test_form').innerHTML;
    const modalRoot = createRoot(document.getElementById('formPopupRoot'));
    modalRoot.render(<ModalPopup bodyHTML={formHTML} />);

    const knockoutRoot = createRoot(document.getElementById('readFromKnockoutRoot'));
    knockoutRoot.render(<ReadFromKnockout inputSelector="#ko-root input" />);

    const outputSpan = document.getElementById('htmlSpan');
    const reactToHTMLRoot = createRoot(document.getElementById('reactToHTMLRoot'));
    reactToHTMLRoot.render(<ReactToHTML outputSpan={outputSpan} />);

    const localTableRoot = createRoot(document.getElementById('localTableRoot'));
    localTableRoot.render(<LocalTable/>);

    const remoteTableRoot = createRoot(document.getElementById('remoteTableRoot'));
    remoteTableRoot.render(<RemoteTable/>);

    const buttonTableRoot = createRoot(document.getElementById('buttonTableRoot'));
    buttonTableRoot.render(<ButtonTable/>);
});