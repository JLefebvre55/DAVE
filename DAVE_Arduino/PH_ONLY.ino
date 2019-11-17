#define A2SLOPE -4.032
#define A2INTERCEPT 14.099

void setup()
{
  Serial.begin(9600);
  
  pinMode(A2, INPUT);
}

 void loop()
 {
  
  printAnalog2(); //print units and skip to next line
  delay(500); //wait between reads
 
 }

void printAnalog2(){
  float voltage=analogRead(A2)/1023.0*5; //convert raw count to voltage (0-5V)
  float sensorValue=-3.838*voltage+13.720; //convert to sensor value with linear calibration equation 
  Serial.print("{\"name\" : \"pH\", \"state\" : ");
  Serial.print(sensorValue);
  Serial.print(", \"V\" : ");
  Serial.print(voltage);
  
  Serial.println("}");
}

 
 
