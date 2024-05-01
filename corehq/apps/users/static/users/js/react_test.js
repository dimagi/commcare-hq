import React from 'react';
import { createRoot } from 'react-dom/client';

function RowClass({row}) {
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

function DisplayTable({rows, RowCls}) {
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
                {rows.map(row => <RowCls key={row.id} row={row} />)}
            </tbody>
        </table>
    );
}

window.addEventListener('load', async () => {
    const url = new URL('/a/first-domain/settings/users/commcare/json/', window.location.origin);
    url.search = new URLSearchParams({
        page: 1,
        limit: 5,
        showDeactivatedUsers: false,
    }) ;

    const users = await fetch(url)
    .then(response => response.json()).then(response => {
        return response.users.map(user => Object.assign(user, {'id': user['user_id']}));
    });
    const root = createRoot(document.getElementById('reactRoot'));
    root.render(<DisplayTable rows={users} RowCls={RowClass} />);
});