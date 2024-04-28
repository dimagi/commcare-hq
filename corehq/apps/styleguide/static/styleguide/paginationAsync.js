import React from 'react';
import { createRoot } from 'react-dom/client';
import Pagination from './pagination';

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

    function Row({item}) {
        return (
            <>{item}</>
        );
    }

    const root = createRoot(document.getElementById('paginationAsyncRoot'));
    root.render(
        <Pagination
            id="pagination-example"
            RowCls={Row}
            getPageItems={getPageItemsAsync}
            slug="pagination-example"
        />
    );
});