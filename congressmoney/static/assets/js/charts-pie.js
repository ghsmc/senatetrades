/**
 * For usage, visit Chart.js docs https://www.chartjs.org/docs/latest/
 */

 tickers = []
 amounts = []
 

 function sum( obj ) {
  var sum = 0;
  for( var el in obj ) {
    if( obj.hasOwnProperty( el ) ) {
      sum += parseFloat( obj[el] );
    }
  }
  return sum;
}
    
var summed = sum( senate_data[official]["top_five_stocks"] );
console.log( "sum: "+summed );
 
let other = parseFloat(senate_data[official]["portfolio_value"].replace(/,/g,'') - summed)

for (let [key, value] of Object.entries(senate_data[official]["top_five_stocks"])) {
  tickers.push(key);
  amounts.push(value);
}

amounts.push(Math.round(other))
tickers.push('other')

amounts.cutoutPercentage


const pieConfig = {
  type: 'doughnut',
  data: {
    datasets: [
      {
        data: amounts,
        /**
         * These colors come from Tailwind CSS palette
         * https://tailwindcss.com/docs/customizing-colors/#default-color-palette
         */
        backgroundColor: ['#34D399', '#059669', '#065F46', '#3B82F6', '#1D4ED8', '#1E3A8A'],
        label: 'Dataset 1',
      },
    ],
    labels: [tickers[0], tickers[1], tickers[2], tickers[3], tickers[4], tickers[5]],
  },
  options: {
    responsive: true,
    cutoutPercentage: 80,
    /**
     * Default legends are ugly and impossible to style.
     * See examples in charts.html to add your own legends
     *  */
    legend: {
      display: true,
    },
  },
}

// change this to the id of your chart element in HMTL
const pieCtx = document.getElementById('pie')
window.myPie = new Chart(pieCtx, pieConfig)
