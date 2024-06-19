import React from 'react';
import { createRoot } from 'react-dom/client';
import { useState } from 'react';
import Button from 'react-bootstrap/Button';
import Modal from 'react-bootstrap/Modal';

export default function ModalPopup({bodyHTML}) {
    const [show, setShow] = useState(false);

    const handleClose = () =>  setShow(false);
    const handleShow = () => setShow(true);

    const markup = { __html: bodyHTML };

    return (
        <>
            <Button variant="primary" onClick={handleShow}>
                Launch demo modal
            </Button>

            <Modal show={show} onHide={handleClose}>
                <Modal.Header closeButton>
                    <Modal.Title>Modal heading</Modal.Title>
                </Modal.Header>
                <Modal.Body dangerouslySetInnerHTML={markup} ></Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={handleClose}>
                        Close
                    </Button>
                    <Button variant="primary" onClick={handleClose}>
                        Save Changes
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
}

window.addEventListener('load', () => {
    const formHTML = document.querySelector('#test_form').innerHTML;
    const modalRoot = createRoot(document.getElementById('formPopupRoot'));
    modalRoot.render(<ModalPopup bodyHTML={formHTML} />);
});
