#include "VernierLib.h" 

VernierLib Vernier;
void setup()
{
  Serial.begin(9600);
  Vernier.autoID();// this is the routine to do the autoID
}

 void loop()
 {
  
  printAnalog1(); //print units and skip to next line
  delay(500); //wait between reads
 
 }

void printAnalog1(){
  //float voltage=analogRead(A0)/1023*5; //convert raw count to voltage (0-5V)
  //float sensorValue=Vernier.slope()*voltage+Vernier.intercept(); //convert to sensor value with linear calibration equation 
  Serial.print("{\"name\" : \"Conductivity\", \"state\" : ");
  Serial.print(Vernier.readSensor());
  Serial.println("}");
}

 
 
