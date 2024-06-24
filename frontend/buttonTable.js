import React from 'react';
import { createRoot } from 'react-dom/client';
import DataTable from 'react-data-table-component';
import Button from 'react-bootstrap/Button';

const columns = [
    {
        name: 'ID',
        selector: row => row.personID,
        sortable: true,
    },
    {
        name: 'Full Name',
        selector: row => row.fullName,
        sortable: true,
    },
    {
        name: 'Action',
        cell: row => <Button onClick={() => alert("Name is: " + row.fullName)}>Download</Button>,
    },
];

const rows = [
    {
        personID: 1,
        fullName: 'Kate Shein',
    },
    {
        personID: 2,
        fullName: "Ava Roberts",
    },
    {
        personID: 3,
        fullName: "Geoffrey Samson Lee",
    },
    {
        personID: 4,
        fullName: "Alex Smith",
    },
    {
        personID: 5,
        fullName: "Leila Nora Jones",
    },
    {
        personID: 6,
        fullName: "Harper Mitchell",
    },
    {
        personID: 7,
        fullName: "Mason Cooper",
    },
    {
        personID: 8,
        fullName: "Hosea Noel Liam Wilson",
    },
    {
        personID: 9,
        fullName: "Yvette Montgomery",
    },
    {
        personID: 10,
        fullName: "Ethan Montgomery",
    },
    {
        personID: 11,
        fullName: "Olivia Parker",
    },
    {
        personID: 12,
        fullName: "Jackson Nguyen",
    },
    {
        personID: 13,
        fullName: "Sophia Ramirez",
    },
    {
        personID: 14,
        fullName: "Elijah Patel",
    },
    {
        personID: 15,
        fullName: "Isabella Thompson",
    },
];

export default function ButtonTable() {
    return (
        <>
            <DataTable
                columns={columns}
                data={rows}
                fixedHeader
                title="React-Data-Table Component Tutorial."
                pagination
            />
        </>
    );
}

window.addEventListener('load', () => {
    const buttonTableRoot = createRoot(document.getElementById('buttonTableRoot'));
    buttonTableRoot.render(<ButtonTable/>);
});
