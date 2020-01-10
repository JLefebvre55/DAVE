/**
* 
*/
const socket = io.connect(window.location.href)

//console.log("test")

var table = document.getElementById("chartTable");

socket.on('chartsetup', function(data) {
	
	console.log("Making first datasets");

	setup = data;
	
	//console.log(data);
	var parent = document.getElementById('allCharts');
	
	//Make chart for each IO input
	setup.sensors.forEach((sensor) => {
		
		
		console.log("Making chart for '"+sensor.name+"'");
		
		/*var heading = document.createElement("h2");
		heading.textContent = sensor.name+" ("+sensor.type.substring(0, 1).toUpperCase()+sensor.type.substring(1).toLowerCase()+")";
		*/
		var div = document.createElement("div");
		div.setAttribute("class", "chart-container");
		var canvas = document.createElement("canvas");
		canvas.setAttribute("id", "chart-"+sensor.name.toLowerCase());
		//div.appendChild(heading);
		div.appendChild(canvas);
		parent.appendChild(div);
		
		var color = '#'+(Math.random()*0xFFFFFF<<0).toString(16);
		
		//Makes generic newchart
		var newchart = new Chart(canvas, {
			// The type of chart we want to create
			type: 'line',
			// The data for our dataset
			data: {
				labels: [],
				datasets: []
			},
			// Configuration options go here
			options: {
				title: {
					display: true,
					text: sensor.name
				}					
			}
			
		});
		
		newchart.data.datasets.push({
			label: sensor.name,
			backgroundColor: color,
			borderColor: color,
			data: [],
			fill: false,
			pointStyle: 'circle',
			pointRadius: 5,
			pointHoverRadius: 7,
			steppedLine: true
		});
		newchart.options.scales.xAxes[0].display = true;
		newchart.options.scales.xAxes[0].labelString = 'Time';
		newchart.options.scales.yAxes[0].display = true;
		newchart.options.scales.yAxes[0].scaleLabel.display = true;
		newchart.options.scales.yAxes[0].scaleLabel.labelString = 'Sensor Read';
		newchart.options.scales.yAxes[0].ticks.min = sensor.min;
		newchart.options.scales.yAxes[0].ticks.max = sensor.max;
		newchart.options.scales.yAxes[0].ticks.stepSize = (sensor.max-sensor.min)/6;
		
		charts.push({id: sensor.name, chart: newchart});
	})
})

socket.on('chartdata', function(data) { //As an arduino io dataset is received 
	
	console.log(data)
	
	if(!setup){
		console.log("setup has not yet been performed!")
	} else {
		
		data.sensors.forEach((sensor)=>{
			console.log("Doing chart stuff for sensor '"+sensor.name+"'...")
			var chartmatch = charts.find(chart => chart.id == sensor.name);
			//console.log("Found "+chartmatch)
			chartmatch.chart.data.datasets[0].data.push(sensor.state);
			chartmatch.chart.data.labels.push(data.time);
		});
		
		charts.forEach((chart)=>{
			while(chart.chart.data.datasets[0].data.length > maxticks){
				chart.chart.data.labels.shift(); //Remove first time data
				chart.chart.data.datasets[0].data.shift();
			}
			chart.chart.update(); //Update the graph.
		})
	}
});