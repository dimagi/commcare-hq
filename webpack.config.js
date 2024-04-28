const path = require('path');

module.exports = {
    entry: {
        'reactExamples': './frontend/reactExamples.js',
        'mobileWorkers': './corehq/apps/users/static/users/js/react_test.js',
        'pagination': './corehq/apps/styleguide/static/styleguide/paginationExamples.js',
    },
    output: {
        filename: '[name].js',
        path: path.resolve(__dirname, './static_react'),
    },
    module: {
        rules: [
            {
                test: /\.(js|jsx)$/,
                exclude: /node_modules/,
                loader: 'babel-loader',
                options: { presets: ['@babel/preset-env', '@babel/preset-react'] },
            },
        ],
    },
};