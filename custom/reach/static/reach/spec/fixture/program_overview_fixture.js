hqDefine('reach/spec/fixture/program_overview_fixture', function () {
    return {
        indicators: {
            data: [
                [
                    {
                        indicator: 'Registered Eligible Couples',
                        format: 'numeric',
                        color: '#8A2BE2',
                        numerator: 71682,
                        denominator: 140098,
                        past_month_numerator: 69354,
                        past_month_denominator: 130098
                    },
                    {
                        indicator: 'Registered Pregnancies',
                        format: 'numeric',
                        color: '#00BFFF',
                        numerator: 9908,
                        denominator: 128990,
                        past_month_numerator: 12458,
                        past_month_denominator: 115800
                    },
                    {
                        indicator: 'Registered Children',
                        format: 'numeric',
                        color: '#FFA500',
                        numerator: 21630,
                        denominator: 890743,
                        past_month_numerator: 40687,
                        past_month_denominator: 715486
                    }
                ],
                [
                    {
                        indicator: 'Couples using Family Planning Method',
                        format: 'percent',
                        color: '#05EDFF',
                        numerator: 65028,
                        denominator: 928103,
                        past_month_numerator: 60486,
                        past_month_denominator: 914384
                    },
                    {
                        indicator: 'High Risk Pregnancies',
                        format: 'percent',
                        color: '#FF8C00',
                        numerator: 207,
                        denominator: 9908,
                        past_month_numerator: 204,
                        past_month_denominator: 9837
                    },
                    {
                        indicator: 'Institutional Deliveries',
                        format: 'percent',
                        color: '#0000CD',
                        numerator: 14311,
                        denominator: 21837,
                        past_month_numerator: 16486,
                        past_month_denominator: 21648
                    }
                ]
            ]
        },
        expectedValues: [
            {
                indicator: 'Registered Eligible Couples',
                format: 'numeric',
                color: '#8A2BE2',
                numerator: 71682,
                denominator: 140098,
                pastMonthNumerator: 69354,
                pastMonthDenominator: 130098,
                isNumeric: true,
                isPercent: false,
                indiaFormat: '71,682',
                diffBetweenMonths: '(-4.02% from last month)'
            },
            {
                indicator: 'Registered Pregnancies',
                format: 'numeric',
                color: '#00BFFF',
                numerator: 9908,
                denominator: 128990,
                pastMonthNumerator: 12458,
                pastMonthDenominator: 115800,
                isNumeric: true,
                isPercent: false,
                indiaFormat: '9,908',
                diffBetweenMonths: '(-28.60% from last month)'
            },
            {
                indicator: 'Registered Children',
                format: 'numeric',
                color: '#FFA500',
                numerator: 21630,
                denominator: 890743,
                pastMonthNumerator: 40687,
                pastMonthDenominator: 715486,
                isNumeric: true,
                isPercent: false,
                indiaFormat: '21,630',
                diffBetweenMonths: '(-57.30% from last month)'
            },
            {
                indicator: 'Couples using Family Planning Method',
                format: 'percent',
                color: '#05EDFF',
                numerator: 65028,
                denominator: 928103,
                pastMonthNumerator: 60486,
                pastMonthDenominator: 914384,
                isNumeric: false,
                isPercent: true,
                percentFormat: '7.01 %',
                secondValueFormat: '65,028 / 9,28,103',
                diffBetweenMonths: '(+5.92% from last month)'
            },
            {
                indicator: 'High Risk Pregnancies',
                format: 'percent',
                color: '#FF8C00',
                numerator: 207,
                denominator: 9908,
                pastMonthNumerator: 204,
                pastMonthDenominator: 9837,
                isNumeric: false,
                isPercent: true,
                percentFormat: '2.09 %',
                secondValueFormat: '207 / 9,908',
                diffBetweenMonths: '(+0.74% from last month)'
            },
            {
                indicator: 'Institutional Deliveries',
                format: 'percent',
                color: '#0000CD',
                numerator: 14311,
                denominator: 21837,
                pastMonthNumerator: 16486,
                pastMonthDenominator: 21648,
                isNumeric: false,
                isPercent: true,
                percentFormat: '65.54 %',
                secondValueFormat: '14,311 / 21,837',
                diffBetweenMonths: '(-13.94% from last month)'
            }
        ]
    }
});
