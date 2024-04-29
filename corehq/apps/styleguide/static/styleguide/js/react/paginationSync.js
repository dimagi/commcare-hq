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

    function Row({item}) {
        return (
            <>{item}</>
        );
    }

    const root = createRoot(document.getElementById('paginationSyncRoot'));
    root.render(
        <Pagination
            id="pagination-example"
            RowCls={Row}
            getPageItems={getPageItems}
            slug="pagination-example"
        />
    );
});