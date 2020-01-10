/*
* 
*/

//Requirements
const express = require('express');
const app = express();
const port = 80;

const path = require('path');
const http = require('http');
const mysql = require('mysql');
const socket = require('socket.io');
const fs = require('fs');

var server = http.createServer(app).listen(port, function(){
	console.log("Express server created - listening on port " + port+"\n");
});

var socketlistener = socket.listen(server);
const NUMROWS = 10

//File GETs
app.get('/', (request, response) => {
	response.sendFile(path.join(__dirname+'/index.html'));
});

app.get('/iochart.js', (request, response) => {
	response.sendFile(path.join(__dirname+'/iochart.js'));
});

app.get('/style.css', (request, response) => {
	response.sendFile(path.join(__dirname+'/style.css'));
});

var databaseLogin = JSON.parse(fs.readFileSync('database.json'));

var database = mysql.createConnection(databaseLogin);

database.connect(function(err) {
	if (err) throw err;
	console.log("Connected to database!");
});

function getData(rows){
	console.log("Collecting last "+rows+" from database...")
	latest = database.query("SELECT id FROM sensordata", function (err, result) {
		if (err) throw err;
		return result;
	});
	console.log("Latest entry id: "+latest);
	data = [];
	var i;
	for(i = latest-rows+1; i <= latest; i++){
		temp = database.query("SELECT * FROM sensordata WHERE id = "+i, function (err, result) {
			if (err) throw err;
			return result;
		});
		console.log("Retrieved row "+i+" from database.")
		console.log(temp)
		data.push(temp)
	}
	console.log("All data collected.")
}

//On socket connect
socketlistener.on('connection', (socket) => {
	console.log("Someone connected: "+socket.id);
	data = getData(NUMROWS);
	socket.emit('data', data);
	console.log("Pushed data to socket.")
});