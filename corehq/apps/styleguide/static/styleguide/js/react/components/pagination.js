import React from 'react';
import { useState, useEffect } from 'react';
import _ from 'underscore';
import Cookies from 'universal-cookie';


const pageSizes = [5, 25, 50, 100];

function Summary({start, end, total}) {
    return (
        <div className="input-group-text">
            Showing {start} to {end} of {total} entries
        </div>
    );
}

function PageSizeControl({pageSize, sizes, setPageSize}) {
    return (
        <select className="form-select" value={pageSize} onChange={e => setPageSize(parseInt(e.target.value, 10))}>
            {
                sizes.map(size => <option key={size} value={size}>{size} per page</option>)
            }
        </select>
    );
}

function StatusDisplay({start, total, pageSize, sizes, setPageSize}) {
    const end = Math.min(start + pageSize - 1, total);
    return (
        <div>
            <div className="input-group">
                <Summary start={start} end={end} total={total} />
                <PageSizeControl pageSize={pageSize} sizes={sizes} setPageSize={setPageSize} />
            </div>
        </div>
    );
}

function PageControl({currentPage, pageSize, totalItems, goToPage, isLoading=true, maxPagesShown=9}) {
    const numPages = Math.ceil(totalItems / pageSize);
    const pagesOnSide = Math.floor(maxPagesShown / 2);
    const lowerBound = Math.max(currentPage - pagesOnSide, 1);
    const upperBound = Math.min(currentPage + pagesOnSide, numPages) + 1;
    const pages = _.range(lowerBound, upperBound);

    const goToPrevious = () => goToPage(Math.max(currentPage - 1, 1));
    const goToNext = () => goToPage(Math.min(currentPage + 1, numPages));

    return (
        <nav aria-label="Page navigation example">
            <ul className="pagination">
                <li className="page-item">
                    <a
                        className="page-link"
                        aria-label="Previous"
                        onClick={goToPrevious}
                    >
                        <span aria-hidden="true">Previous</span>
                    </a>
                </li>
                {pages.map(pageNum =>
                    <li
                        className={pageNum === currentPage ? "page-item active" : "page-item"}
                        aria-current={pageNum === currentPage ? "page" : null}
                        key={pageNum}
                    >
                        <a className="page-link" onClick={() => goToPage(pageNum)}>
                            {pageNum === currentPage && isLoading ?
                                <i className="fa fa-spin fa-spinner"></i> : <span>{pageNum}</span>
                            }
                        </a>
                    </li>
                )}
                <li className="page-item">
                    <a
                        className="page-link"
                        aria-label="Next"
                        onClick={goToNext}
                    >
                        <span aria-hidden="hidden">Next</span>
                    </a>
                </li>
            </ul>
        </nav>
    );
}

const cookies = new Cookies();

function getPageSizeCookieName(slug) {
    return 'ko-pagination-' + slug;  // Unfortunate that knockout is part of this cookie's name
}

function getInitialPageSize(slug, value, inlinePageListOnly) {
    if (!slug || inlinePageListOnly) {
        return value;
    }

    const cookieName = getPageSizeCookieName(slug);
    const cookieValue = parseInt(cookies.get(cookieName), 10);
    return cookieValue || value;
}

function updatePageSizeCookie(slug, value) {
    if (!slug) {
        return;
    }

    const cookieName = getPageSizeCookieName(slug);
    const expirationDate = new Date();
    expirationDate.setFullYear(expirationDate.getFullYear() + 1);
    // secure should probably be set through a context
    cookies.set(cookieName, value, { expires: expirationDate, path: '/', secure: false});
}

/**
 *  React Pagination Component
 *
 *  Include the <Pagination> element on your JSX page with the following parameters:
 *      DisplayCls: A JSX component that will display your collection. Expected props are {items, getItemId}
 *          where items are the items to be displayed and getItemId resolves an item into a unique identifier
 *      getPageItems: A function or promise to return a page's items. Requires pageNum and pageSize parameters,
 *          and must return an object containing with 'items' and 'totalItemCount' keys.
 *      inlinePageListOnly: Optional. True or false. If true, leave off the "Showing X to Y of Z entries"
 *          text and the associated dropdown.
 *      id: Optional. An id that will be applied to the native HTML container
 *      slug: Optional. A string unique among pagination widgets. If provided, used to save perPage value
 *          in a cookie.
 */
export default function Pagination({DisplayCls, getItemId, getPageItems, id, slug, inlinePageListOnly}) {
    let [pageSize, setPageSize] = useState(() => getInitialPageSize(slug, 5, inlinePageListOnly));
    let [items, setItems] = useState([]);
    let [totalItemCount, setTotalItemCount] = useState(0);
    let [page, setPage] = useState(1);
    let [isLoading, setIsLoading] = useState(false);


    const updatePage = (page) => {
        setIsLoading(true);
        setPage(page);
        Promise.resolve(getPageItems(page, pageSize))
            .then(({items, totalItemCount}) => {
                setItems(items);
                setTotalItemCount(totalItemCount);
            })
            .finally(() => {
                setIsLoading(false);
            });
    };

    const updatePageSize = (pageSize) => {
        const newPage = 1; // reset to the first page on every page change
        setIsLoading(true);
        setPage(newPage);
        Promise.resolve(getPageItems(newPage, pageSize))
            .then(({items, totalItemCount}) => {
                setPageSize(pageSize);
                setItems(items);
                setTotalItemCount(totalItemCount);
                updatePageSizeCookie(slug, pageSize);
            })
            .finally(() => {
                setIsLoading(false);
            });
    };

    useEffect(() => {
        updatePage(page);
    }, []);

    const offset = pageSize * (page - 1);

    return (
        <div id={id}>
            <DisplayCls rows={items} getItemId={getItemId} />
            { !inlinePageListOnly &&
                <div className="py-3 d-flex justify-content-between">
                    <StatusDisplay start={offset + 1} total={totalItemCount} pageSize={pageSize} sizes={pageSizes} setPageSize={updatePageSize} />
                    <PageControl currentPage={page} pageSize={pageSize} totalItems={totalItemCount} goToPage={updatePage} isLoading={isLoading} />
                </div>
            }
        </div>
    );
}
