
#include "VernierLib.h" 
#define A2SLOPE -3.97477
#define A2INTERCEPT 13.8162                                         

VernierLib Vernier;
void setup()
{
  Serial.begin(9600);
  Vernier.autoID();// this is the routine to do the autoID
  pinMode(A2, INPUT);
}

void loop()
{
  Serial.print("[");
  printAnalog1(); //print sensor value 
  Serial.print(",");
  printAnalog2(); //print units and skip to next line
  Serial.println("]");
  delay(1000); //wait between reads

}

void printAnalog2(){
  float voltage=analogRead(A2)/1023.0*5; //convert raw count to voltage (0-5V)
  float sensorValue=A2SLOPE*voltage+A2INTERCEPT; //convert to sensor value with linear calibration equation 
  Serial.print("{\"name\" : \"pH\", \"state\" : ");
  Serial.print(sensorValue);
  Serial.print("}");
  Serial.print(voltage);
}


void printAnalog1(){
  //float voltage=analogRead(A0)/1023*5; //convert raw count to voltage (0-5V)
  //float sensorValue=Vernier.slope()*voltage+Vernier.intercept(); //convert to sensor value with linear calibration equation 
  Serial.print("{\"name\" : \"EC\", \"state\" : ");
  Serial.print(Vernier.readSensor());
  Serial.print("}");
}



