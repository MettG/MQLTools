//+------------------------------------------------------------------+
//|                                                     TrailBoi.mq4 |
//|                                 Tristan Johnson Advance Momentum |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+


// TO Do
/*
   Enter 

*/
//

#property copyright "Tristan Johnson Advance Momentum"
#property link      "https://www.mql5.com"
#property version   "1.03"
#define INFO "Position types, automatic entries"
#property strict
#define POS_TYPE_MEAN 0
#define POS_TYPE_TREND 1

extern int RISK_PERCENT = 5;
extern double STOP_MULT = 1;
extern double TAKE_MULT = 1;
extern double TRAIL_MULT = 0.25;

extern int MEAN_PERIOD = 8;
extern int ATR_PERIOD = 20;

int tickets[]; // These are the tickets that have a take profit, other tickets are runners
string symb;
int tf;
double last_distance;

class VirtualStop{
   public:
      double price;
      int ticket;
      VirtualStop(int openPositionTicket, double stopPrice){
         ticket = openPositionTicket;
         price = stopPrice;
      }
      bool Update(){
         if(!OrderSelect(ticket,SELECT_BY_TICKET)){
            Print("Virtual Stop @", price, " Position does not exist. Removing.");
            return false;
         } else{
            if(OrderCloseTime != 0){
               Print("Position is closed on ", OrderSymbol(), "Removing virtual stop");
               return false;
            }

            if((OrderType() == 0 && Bid < price) || (OrderType() == 1 && Ask > price)){
               if(!OrderClose(ticket,OrderLots(), price, 5, Red)){
                  Alert("Error when trying to close position @", price, " Error:", GetLastError());
               }else{
                  Print("Position successfully closed at virtual stop.");
               }
            }
         }
         return true;
      }
};


VirtualStop * virtualStop;


double WMA(double &arr[], int y, int start=0){
   double norm = 0.0;
   double sum = 0.0;
   for(int i = 0; i < y ; i++;) {
      double weight = (y - i) * y;
      norm = norm + weight;
      sum = sum + arr[i+start] * weight;
   }
   return sum / norm;
}


// A : WMA(closes, length/2) B: WMA(closes,length) C: WMA(2A-B, sqrt length)

double HMA(src,length){
   int outLen = MathFloor(MathSqrt(length));
   int firstLen = MathRound(length/2);
   double c[];
   double b[];
   double a[]
   double closes[];
   ArrayResize(c,outLen, outLen);
   ArrayResize(b,outLen, length);
   ArrayResize(a,outLen, firstLen);
   // Fill B & A
   for(int i = 0; i < length; i++){
      
   }

   // Fill C

   return WMA(2*WMA(closes, firstLen)-WMA(closes, length), outLen);
}

bool TargetHit(double open, datetime time, int type, double dist ){
   int i = 0;
   Print("Checking if target was hit. Current time: ", Time[i], " Open time: ", time);
   while(Time[i] >= time){
      i++;
      bool further= type == 0 && High[i] - open >= dist? true : type == 1 && open - Low[i] >= dist? true: false;
      
      if(further){
         Print("Target has been hit!");
         return true;
      }
   }
   return false;
}

bool SymbolHasTargetPos(){
   Sleep(600); // Give the server a chance to catch up with any new orders
   // Check if all positions with take are still open
   int new_tickets[];
   bool has_pos_with_tp = false;
   for(int j = 0; j < ArraySize(tickets); j++){
      bool found = false;
      int ticket = 0;
      for(int i = 0; i < OrdersTotal(); i++){
         if(OrderSelect(i, SELECT_BY_POS)){
            ticket = OrderTicket();
            if(OrderSymbol() != symb)continue;
            if(OrderTakeProfit() != 0) has_pos_with_tp = true;
            if(ticket == tickets[j]){
               found = true;
               break;
            }
         }
      }
      if(found){
         int temp[];
         int size = ArraySize(new_tickets);
         ArrayResize(temp, size+1, size+1);
         ArrayCopy(temp, new_tickets);
         temp[size] = ticket;
         ArrayCopy(new_tickets,temp);
      }
   }
   int corrected_size = ArraySize(new_tickets);
   // Copy over the corrected ticket Array
   ArrayResize(tickets, corrected_size, corrected_size);
   ArrayCopy(tickets, new_tickets);
   return has_pos_with_tp;
}

void AddTargetPosition(int t){

   // Add the new ticket
   int temp[];
   int size = ArraySize(tickets);
   ArrayResize(temp, size+1, size+1);
   ArrayCopy(temp, tickets);
   temp[size] = t;
   ArrayCopy(tickets, temp);
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//---
   symb = Symbol();
   tf = Period();
   last_distance = (Ask - Bid) / 2;
   Print("Trail Boy Online.");
   Print(INFO);
//---
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
//---
   
  }
  
  
  
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
//---
   double mean = HMA(Close,MEAN_PERIOD);
   double std = iStdDev(symb, tf, ATR_PERIOD, 0, MODE_SMA, PRICE_CLOSE, 0);
   double atr = iATR(symb,60,ATR_PERIOD,1);
   double curr_price = (Ask - Bid) / 2;
   // Run manage positions on price change or new entry Object
   if (MathAbs(curr_price - last_distance) > 10*Point || NewEntryObject()){

      Print("Updating Virtual Stops.");
      if(virtualStop != NULL){
         if(!virtualStop.Update()) {
            Print("Virtual stop filled.");
            delete virtualStop;
            virtualStop = NULL;
         }
      }
      ManagePositions(symb, STOP_MULT * atr, TAKE_MULT * atr, TRAIL_MULT * atr, mean, atr, std);
      last_distance = curr_price;           
   }
  }
//+------------------------------------------------------------------+

double FlatDouble(double d, int digs){
   return MathFloor(d * MathPow(10, digs)) / MathPow(10, digs);
}

void ManagePositions(string sym, double sd, double td, double trail, double mean, double a, double std){
   for(int i = 0; i < OrdersTotal(); i++){
      if(OrderSelect(i,SELECT_BY_POS)){
         if(OrderSymbol() != sym) continue;
         int type = OrderType();
         if(type > 1) continue;
         double price = type == 0 ? Ask : Bid;
         // Check if have stops
         double open = OrderOpenPrice();
         double take = OrderTakeProfit();
         int ticket = OrderTicket();
         double stop = OrderStopLoss();
         datetime openTime = OrderOpenTime();
         double distance = type == 0 ? price - mean : mean - price;
         double spread = Ask - Bid;
         bool targetHit = TargetHit(open, openTime, type, FlatDouble(td, Digits));
         double new_stop = stop;
         
         // Check position type. Assume mean reversion unless comment specifies
         string comment = OrderComment();
         int posType = POS_TYPE_MEAN;

         // Construct hma bands
         double upperBand = mean + std;
         double lowerBand = mean - std;
         
         if(comment == "trend") {
            posType = POS_TYPE_TREND;
         } 

         // ==================
         // MEAN REVERSION POSITION
         // ==================

         if(posType == POS_TYPE_MEAN){
            print("Open position on ", sym, " is a mean reversion.");
            // BUY POSITION
            if(type == 0) {

               if(stop == 0) {
                  // Set buy stop
               }

               // check if price has reached upper band, move stop to low.
               if(High[0] >= upperBand){
                  new_stop = Low[1];
               }
               // check if price has closed passed mean, move stop to break even, or just above mean, whichever is further in profit.
               else if(Close[1] > mean){
                  new_stop = mean - spread;
                  if(new_stop < stop) {
                     new_stop = stop;
                  } else if(new_stop < open + 2 * spread){
                     new_stop = open + 2 * spread;
                  }
               }

            }
            // SELL POSITION
            else if(type == 1){
               //check if price has reached lower band, move stop to high

               if(stop == 0){
                  // Set sell stop
               }

               if(Low[0] <= lowerBand){
                  new_stop = High[1];
               }
               else if(Close[1] < mean) {
                  new_stop = mean + spread;
                  if(new_stop > stop) {
                     new_stop = stop;
                  } else if(new_stop > open - 2 * spread){
                     new_stop = open - 2 * spread;
                  }
               }
            }

         }

         // =================
         // TREND POSITION
         // ================

         else if (posType == POS_TYPE_TREND) {
            // Check if no take and not the runner order
            if(take == 0 && !SymbolHasTargetPos() && !targetHit){
               take = type == 0 ? open + td: open - td;
               take = FlatDouble(take, Digits);
               Print("Not a runner order, adding take. ", take);
            }

            // Check if no stop
            if(stop == 0){
               new_stop = type == 0 ? FlatDouble(open - sd, Digits): FlatDouble(open + sd, Digits);
               Print("No stop detected, adding ", new_stop);
               positive = true;
            }

            if(type == 0){
               bool even_triggered = false;
               if(High[1] - mean >= a) {
                  Print("Buy Break even triggered.");
                  new_stop = open + 2 * spread;
                  even_triggered = true;
               }
               if(Bid >= mean + std + a){
                  Print("Position is far away from mean in buy direction.");
                  new_stop = Bid - a;
               }
               else if(Bid > mean){
                  Print("Position is on positive side of mean, in buy direction.");
                  new_stop = mean - std;
               } else if (Bid < mean){
                  Print("Position is on negative side of mean, in buy direction.");
                  new_stop = mean - std - .3 * a;
               }
               if(new_stop < stop || (!even_triggered && new_stop < open + std)) new_stop = stop;

            } else if(type == 1){
               bool even_triggered = false;
               if(mean - Low[1] >= a) {
                  Print("Sell Break even triggered.");
                  new_stop = open - 2 * spread;
                  even_triggered = true;
               }
               if(Ask <= mean - std - a){
                  Print("Position is far away from mean in sell direction.");
                  new_stop = Ask + a;
               }
               else if(Ask < Mean){
                  Print("Position is on positive side of mean, in sell direction.");
                  new_stop = mean + std;
               } else if (Ask > mean){
                  Print("Position is on negative side of mean, in sell direction.");
                  new_stop = mean + std + .3 * a;
               }
               if(new_stop > stop || (!even_triggered && new_stop > open - std)) new_stop = stop;
            }

            if(take != 0) {
               AddTargetPosition(ticket);
            }
         }

         // Update stops if necessary 
         if(new_stop != stop){
            double min_dist = MarketInfo(symb,MODE_STOPLEVEL) * Point;
            if(take != 0) take = type == 0 && take - Ask < min_dist ? Ask + min_dist : type == 1 && Bid - take < min_dist? Bid - min_dist : take;
            new_stop = type == 0 && Bid - new_stop < min_dist ? Bid - min_dist : type == 1 && new_stop - Ask < min_dist? Ask + min_dist : new_stop;
            if(!OrderModify(ticket, open, new_stop, take,0)){
               int e = GetLastError();
               if(e > 1) Alert("Error Modifying order! ", e);
               Print("Building new virtual stop.")
               virtualStop = new VirtualStop(ticket, new_stop);
            } else{
               Print("Order successfully updated.")
            }
         }
      }
   }
   Print("Done.");
} 