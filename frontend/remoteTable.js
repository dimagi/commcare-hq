import React from 'react';
import { createRoot } from 'react-dom/client';
import { useState, useEffect } from 'react';
import DataTable from 'react-data-table-component';

const newColumns = [
    {
        name: 'Case Type',
        selector: row => row[0],
        sortable: true,
    },
    {
        name: 'Name',
        selector: row => row[1],
        sortable: true,
    },
    {
        name: 'Color',
        selector: row => row[2],
        sortable: true,
    },
    {
        name: 'Big Cats',
        selector: row => row[3],
        sortable: true,
    },
    {
        name: 'Date of Birth',
        selector: row => row[4],
        sortable: true,
    },
    {
        name: 'Application',
        selector: row => row[5],
        sortable: true,
    },
    {
        name: 'Opened On',
        selector: row => row[6],
        sortable: true,
    },
    {
        name: 'Owner',
        selector: row => row[7],
        sortable: true,
    },
    {
        name: 'Status',
        selector: row => row[8],
        sortable: true,
    },
];

export default function RemoteTable() {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [totalRows, setTotalRows] = useState(0);
    const [perPage, setPerPage] = useState(10);
    const fetchData = async page => {
        setLoading(true);
        const response = await fetch(`/styleguide/b5/data/paginated_table_data?page=${page}&limit=${perPage}`);
        const result = await response.json();
        setData(result.rows);
        setTotalRows(result.total);
        setLoading(false);
    };

    const handlePageChange = page => {
        fetchData(page);
    };

    const handlePerRowsChange = async (newPerPage, page) =>  {
        setLoading(true);
        const response = await fetch(`/styleguide/b5/data/paginated_table_data?page=${page}&limit=${newPerPage}`)
        const result = await response.json();
        setData(result.rows);
        setPerPage(newPerPage);
        setLoading(false);
    };

    useEffect(() => {
        fetchData(1);
    }, []);

    return (
        <DataTable
            title="Users"
            columns={newColumns}
            data={data}
            progressPending={loading}
            pagination
            paginationServer
            paginationTotalRows={totalRows}
            onChangeRowsPerPage={handlePerRowsChange}
            onChangePage={handlePageChange}
        />
    );
}

window.addEventListener('load', () => {
    const remoteTableRoot = createRoot(document.getElementById('remoteTableRoot'));
    remoteTableRoot.render(<RemoteTable/>);
});