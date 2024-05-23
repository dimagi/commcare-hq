import React from 'react';
import { createRoot } from 'react-dom/client';
import _ from 'underscore';
import Pagination from 'HQ/styleguide/components/pagination.js';

function RowDisplay({row}) {
    return (
        <tr>
            <td>
                <a href={row.edit_url}>
                    <i className="fa fa-user"></i>
                    <strong>{row.username}</strong>
                </a>
            </td>
            <td>{row.first_name}</td>
            <td>{row.last_name}</td>
            <td>{row.date_registered}</td>
            <td>
                <div>
                    <button
                        type="button"
                        className="btn btn-default"
                        data-toggle="modal"
                        data-target={`#deactivate_${row.user_id}`}
                    >
                        Deactivate
                    </button>
                </div>
            </td>
        </tr>
    );
}

function TableDisplay({rows, getItemId}) {
    return (
        <table className="table table-striped table-responsive" style={{marginBottom: 0}}>
            <thead>
                <tr>
                    <th className="col-xs-3">Username</th>
                    <th className="col-xs-3">First Name</th>
                    <th className="col-xs-2">Last Name</th>
                    <th className="col-xs-2">Date Registered</th>
                    <th className="col-xs-2">Action</th>
                </tr>
            </thead>
            <tbody>
                {rows.map(row => <RowDisplay key={getItemId(row)} row={row} />)}
            </tbody>
        </table>
    );
}

window.addEventListener('load', async () => {
    const loadRequireLib = (lib) => {
        return new Promise(resolve => {
            window.requirejs([lib], (foundLib) => resolve(foundLib));
        });
    };

    const paginationUrl = await loadRequireLib('hqwebapp/js/initial_page_data')
        .then(initialPageData => initialPageData.reverse('paginate_mobile_workers'));

    const getPageItemsAsync = (pageNum, pageSize) => {
        const url = new URL(paginationUrl, window.location.origin);
        url.search = new URLSearchParams({
            page: pageNum,
            limit: pageSize,
            showDeactivatedUsers: false,
        }) ;

        return fetch(url).then(response => response.json()).then(response => {
            return {
                items: response.users,
                totalItemCount: response.total,
            };
        });
    };


    const getItemId = (item) => item.user_id;
    const root = createRoot(document.getElementById('reactRoot'));
    root.render(
        <Pagination
            id="pagination-example"
            DisplayCls={TableDisplay}
            getItemId={getItemId}
            getPageItems={getPageItemsAsync}
            slug="pagination-example"
        />
    );
});