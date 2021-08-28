/**
 * For usage, visit Chart.js docs https://www.chartjs.org/docs/latest/
 */

xaxis = []
yaxis = []

spy_xaxis = []
spy_yaxis = []

var baseline = senate_data[official]["returns"]["2020-01-01T00:00:00"];

for (let [key, value] of Object.entries(senate_data[official]["returns"])) {
    key = key.substr(0, 10)
    xaxis.push(key);
    if (baseline != 0){
      yaxis.push(value / baseline);
    } else {
      yaxis.push(value)
    }
 
}

for (let [key, value] of Object.entries(senate_data["daily_summary"]["index_returns"])) {
  key = key.substr(0, 10)
  spy_xaxis.push(key);
  spy_yaxis.push(value);
}

console.log(spy_xaxis)
console.log(xaxis)

const lineConfig = {
  type: 'line',
  data: {
    labels: xaxis,
    datasets: [
      {
        label: official,
        /**
         * These colors come from Tailwind CSS palette
         * https://tailwindcss.com/docs/customizing-colors/#default-color-palette
         */
        backgroundColor: '#0694a2',
        borderColor: '#0694a2',
        data: yaxis,
        fill: false,
      },
      {
        label: 'SPY',
        fill: false,
        /**
         * These colors come from Tailwind CSS palette
         * https://tailwindcss.com/docs/customizing-colors/#default-color-palette
         */
        backgroundColor: '#7e3af2',
        borderColor: '#7e3af2',
        data: spy_yaxis,
      },
    ],
  },
  options: {
    responsive: true,
    /**
     * Default legends are ugly and impossible to style.
     * See examples in charts.html to add your own legends
     *  */
    legend: {
      display: false,
    },
    tooltips: {
      mode: 'index',
      intersect: false,
    },
    hover: {
      mode: 'nearest',
      intersect: true,
    },
    scales: {
      x: {
        display: true,
        scaleLabel: {
          display: true,
          labelString: 'Month',
        },
      },
      y: {
        display: true,
        scaleLabel: {
          display: true,
          labelString: 'Value',
        },
      },
    },
  },
}

// change this to the id of your chart element in HMTL
const lineCtx = document.getElementById('line')
window.myLine = new Chart(lineCtx, lineConfig)