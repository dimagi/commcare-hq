import React from 'react';
import { createRoot } from 'react-dom/client';
import { useState } from 'react';
import DataTable from 'react-data-table-component';

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
        name: 'Height',
        selector: row => row.height,
        sortable: true,
    },
    {
        name: 'Eye Color',
        selector: row => row.eyeColor,
        sortable: true,
    },
];

const rows = [
    {
        personID: 1,
        fullName: 'Kate Shein',
        height: '1.79m',
        eyeColor: 'blue',
    },
    {
        personID: 2,
        fullName: "Ava Roberts",
        height: "1.79m",
        eyeColor: "green",
    },
    {
        personID: 3,
        fullName: "Geoffrey Samson Lee",
        height: "1.79m",
        eyeColor: "brown",
    },
    {
        personID: 4,
        fullName: "Alex Smith",
        height: "1.79m",
        eyeColor: "brown",
    },
    {
        personID: 5,
        fullName: "Leila Nora Jones",
        height: "1.79m",
        eyeColor: "brown",
    },
    {
        personID: 6,
        fullName: "Harper Mitchell",
        height: "1.79m",
        eyeColor: "green",
    },
    {
        personID: 7,
        fullName: "Mason Cooper",
        height: "1.79m",
        eyeColor: "blue",
    },
    {
        personID: 8,
        fullName: "Hosea Noel Liam Wilson",
        height: "1.79m",
        eyeColor: "blue",
    },
    {
        personID: 9,
        fullName: "Yvette Montgomery",
        height: "1.79m",
        eyeColor: "green",
    },
    {
        personID: 10,
        fullName: "Ethan Montgomery",
        height: "1.79m",
        eyeColor: "brown",
    },
    {
        personID: 11,
        fullName: "Olivia Parker",
        height: "1.79m",
        eyeColor: "brown",
    },
    {
        personID: 12,
        fullName: "Jackson Nguyen",
        height: "1.79m",
        eyeColor: "brown",
    },
    {
        personID: 13,
        fullName: "Sophia Ramirez",
        height: "1.79m",
        eyeColor: "brown",
    },
    {
        personID: 14,
        fullName: "Elijah Patel",
        height: "1.79m",
        eyeColor: "brown",
    },
    {
        personID: 15,
        fullName: "Isabella Thompson",
        height: "1.79m",
        eyeColor: "blue",
    },
];

export default function LocalTable() {
    const [data, setData] = useState(rows);

    const handleSearch = e => {
        let searchValue;
        let personIDValue;
        let fullNameValue;
        let heightValue;
        let eyeColorValue;

        const newRows = rows.filter((row) => {
            personIDValue = row.personID.toString().toLowerCase().includes(e.target.value.toLowerCase());
            fullNameValue = row.fullName.toLowerCase().includes(e.target.value.toLowerCase());
            heightValue = row.height.toLowerCase().includes(e.target.value.toLowerCase());
            eyeColorValue = row.eyeColor.toLowerCase().includes(e.target.value.toLowerCase());

            if (personIDValue) {
                searchValue = personIDValue;
            } else if (fullNameValue) {
                searchValue = fullNameValue;
            } else if (heightValue) {
                searchValue = heightValue;
            } else {
                searchValue = eyeColorValue;
            }

            return searchValue;
        });

        setData(newRows);
    };


    return (
        <>
            <div className="container my-5">
                <div className="input-group">
                    <input
                        type="search"
                        className="form-control-sm border ps-3"
                        placeholder="Search"
                        onChange={handleSearch}
                    />
                </div>
                <DataTable
                    columns={columns}
                    data={data}
                    fixedHeader
                    title="React-Data-Table Component Tutorial."
                    pagination
                />
            </div>
        </>
    );
}

window.addEventListener('load', () => {
    const localTableRoot = createRoot(document.getElementById('localTableRoot'));
    localTableRoot.render(<LocalTable/>);
});