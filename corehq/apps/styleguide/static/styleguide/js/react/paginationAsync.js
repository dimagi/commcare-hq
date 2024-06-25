import React from 'react';
import { createRoot } from 'react-dom/client';
import Pagination from './components/pagination';

window.addEventListener('load', () => {
    const allItems = _.map(_.range(23), i => `Item #${i + 1}`);
    const getPageItems = (pageNum, pageSize) => {
        return {
            items: allItems.slice(pageSize * (pageNum - 1), pageSize * pageNum),
            totalItemCount: allItems.length,
        };
    };

    const getPageItemsAsync = (pageNum, pageSize) => {
        return new Promise((resolve) => {
            setTimeout(() => {
                resolve(getPageItems(pageNum, pageSize));
            }, 3000);
        });
    };

    function ListDisplay({rows, getItemId}) {
        return (
            <ul className="list-group">
                { rows.map((row) => (
                    <li className="list-group-item" key={getItemId(row)}>
                        {row}
                    </li>
                ))}
            </ul>
        );
    }

    const getItemId = (item) => item;

    const root = createRoot(document.getElementById('paginationAsyncRoot'));
    root.render(
        <Pagination
            id="pagination-example"
            DisplayCls={ListDisplay}
            getItemId={getItemId}
            getPageItems={getPageItemsAsync}
            slug="pagination-example"
        />
    );
});
