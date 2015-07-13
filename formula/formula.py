# Copyright (c) 2015 RainMachine, Green Electronics LLC
# All rights reserved.
# Authors: Csenteri Barna <brown@mini-box.com>
#          Nicu Pavel <npavel@mini-box.com>
#          Codrin Juravle <codrin.juravle@mini-box.com>
#

import math
#Unused parameters should be passed as None
##########################asceDaily#######################################################
#parameters
#        year = 2012
#        month = 11
#   day = 3
#        fTMinC = -1.0 [degC] - min temp of the day
#        fTMaxC = 10.0 [degC] - max temp of the day
#        fU2z = 2.3 [meter/sec] - windspeed 
#        fU2m = 10.0 [meter] - elevation where the windspeed was measured (usually 2 m)
#        fLat = 36.82 [latitude]
#        fElevation = 98.5 [m] - elevation 
#        fRs = 16.502 [MJ m-2 h-1] - measured incoming solar radiation. If == None it is estimated from fKrs and fTMinC/fTMaxC
#        fEa = 1.4 [kPa] - actual vapor pressure. If == None it is estimated from fRHMin, fRHMax or fTDewpointC
#        fRHMin - 11.0 [%] - minimum relative humidity
#        fRHMax - 33.0 [%] - maximum relative humidity
#        fPressure - 1300.0 [kPa] - atmoshperic pressure. If == None it is calculated from elevation
#        fKrs - 0.17 [] - constant used for solar radiation/temperature estimation. If == None the used value is 0.17
#        fTDewpointC = 5.0 [degC] - dewpoint temperature - used for Ea estimation

def asceDaily(year, month, day, fTMinC, fTMaxC, fU2z, fU2m, fLat, fElevation, fRs, fEa, fRHMin, fRHMax, fPressure, fKrs, fTDewpointC):
	#//////////day of year////////////
	fJ = day - 32 + math.floor(275 * month / 9.0) + 2 * math.floor(3.0 / (month + 1)) + math.floor(month / 100.0 - (year % 4) / 4.0 + 0.975);#Eq.25
	#print("->Day of year:", fJ);
	#/////////temperatures////////////
	fTMeanC = (fTMinC + fTMaxC) / 2;
	fTMinK = 273.16 + fTMinC;
	fTMaxK = 273.16 + fTMaxC;
	#print("->TMeanC:", fTMeanC, "TMinK:",fTMinK, "TMaxK:",fTMaxK);
	#/////////delta///////////////////
	fDelta = 2503.0 * math.exp(17.27 * fTMeanC / (fTMeanC + 237.3)) / math.pow(fTMeanC + 237.3, 2);#Eq.5
	#print("->Delta:", fDelta);
	#//////// es /////////////////////
	fETMax = 0.6108 * math.exp(17.27 * fTMaxC / (fTMaxC + 237.3));#Eq.7
	fETMin = 0.6108 * math.exp(17.27 * fTMinC / (fTMinC + 237.3));#Eq.7
	fEs = (fETMax + fETMin) / 2;#Eq.6
	if fEa == None:
		if fRHMax != None:
			if fRHMin != None:
				fEa = (fETMax * fRHMin / 100 + fETMin * fRHMax / 100) / 2;#Eq.11 Ea from relative humidity
			else:
				fEa = fETMin * fRHMax / 100;#Eq.18 from FAO56.pdf (simpliefied Eq.11)
		else:
			if fTDewpointC != None:
				fEa = 0.6108 * math.exp(17.27 * fTDewpointC / (fTDewpointC + 237.3));#Eq.8 Ea from TDew
			else:
				fEa = 0.6108 * math.exp(17.27 * fTMinC / (fTMinC + 237.3));#Eq.8 Ea from TDew aproximated with TMin
	#print("->Ea:", fEa, "Es:", fEs);
	#////////u2//////////////////////
	fU2 = 0.0;#default value 0 m/s (no wind)
	if fU2m == None:
		fU2m = 2;#by default wind is measured at 2m height
	if fU2z != None:
		fU2 = fU2z * 4.87 / math.log(67.8 * fU2m - 5.42);#Eq.33
	#print("->Wind at 2m:", fU2);
	#////////dr//////////////////////
	fDr = 1.0 + 0.033 * math.cos(2 * math.pi / 365 * fJ);#Eq.23
	#print("->Dr:", fDr);
	#////////declin//////////////////////
	fDeclin = 0.409 * math.sin(2 * math.pi / 365 * fJ - 1.39);#Eq.24
	#print("->Declin:", fDeclin);
	#///////omegas///////////////////////
	fLatRadian = math.pi / 180.0 * fLat;
	#print "->Lat Radian:", fLatRadian;
	fOmegaPreprocess = -math.tan(fLatRadian) * math.tan(fDeclin);
	#print "->OmegaPreprocess:", fOmegaPreprocess;
	if fOmegaPreprocess > 1.0:
		fOmegaPreprocess = 1.0;
	else:
		if fOmegaPreprocess < -1.0:
			fOmegaPreprocess = -1.0;
	fOmegaS = math.acos(fOmegaPreprocess);#Eq.27
	#print("->OmegaS:", fOmegaS);
	#////////radiation stuff ////////////
	fRa = 24.0 / math.pi * 4.92 * fDr * (fOmegaS * math.sin(fLatRadian) * math.sin(fDeclin) + math.cos(fLatRadian) * math.cos(fDeclin) * math.sin(fOmegaS) );#Eq.21
	fRSo = 0.0;
	if fElevation != None:
		fRSo = (0.75 + 2.0 * fElevation / 100000.0) * fRa;#Eq.19
	else:
		fRSo = 0.75 * fRa;#dumb aproximation

	#if fRs is not valid, calculate it from temperatures
	if fKrs == None:
		fKrs = 0.17;

	if fRs == None:
		fRs = fKrs * math.sqrt(fTMaxC - fTMinC) * fRa;#eq 4/appendix.pdf
		if fRs < 0:
			fRs = 0;
		if fRs > fRSo:
			fRs = fRSo;
		#fRs = fRSo;//0.75*Ra (Eq. E.2/appendix)

	if fRSo != 0:
		fFcd = 1.35 * fRs / fRSo - 0.35;
	else:
		fFcd = 0.05;
	if (fRSo == 0):
		fFcd = 0;
	if (fFcd < 0.05):
		fFcd = 0.05;
	if (fFcd > 1):
		fFcd = 1.0;

	SIGMA_DAY = 0.000000004901;
	fRnl = SIGMA_DAY * ((math.pow(fTMinK, 4) + math.pow(fTMaxK, 4)) / 2) * fFcd * (0.34 - 0.14 * math.sqrt(fEa));#Eq.17

	#todo - fRs = UNUSED
	fRns = 0.77 * fRs;#Eq.16
	fRn = fRns - fRnl;#Eq.15

	#print("->Ra:", fRa, "Rso:", fRSo, "Rnl:", fRnl);
	#print("->Rns:", fRns, "Rn:", fRn);

	#///////////Pressure//////////////////
	if fPressure == None:
		fPressure = 101.3 * pow((293 - 0.0065 * fElevation) / 293, 5.25);#Eq.3
	PSYCON = 0.000665;
	fPsyCon = PSYCON * fPressure;#Eq.4
	#print("->Pressure:", fPressure);

	#///////////ET//////////////////
	fCn = 900.0;
	fCd = 0.34;
	fETos = 0.408 * fDelta * fRn + fPsyCon * fCn / (fTMeanC + 273) * fU2 * (fEs - fEa);
	fETos = fETos / (fDelta + fPsyCon * (1 + fCd * fU2) );

	fCn = 1600;
	fCd = 0.38;
	fETrs = 0.408 * fDelta * fRn + fPsyCon * fCn / (fTMeanC + 273) * fU2 * (fEs - fEa);
	fETrs = fETrs / (fDelta + fPsyCon * (1 + fCd * fU2) );

	if fETos < 0.0: # don't allow negative ET0
		fETos = 0.0

	#print("->ETos:", fETos, "ETrs:", fETrs);

	return fETos;

##########################end of asceDaily#######################################################
# Test code
if __name__ == '__main__':
	#               year  ,month,day  ,minT ,maxT ,wind ,windalt,lat deg,elev(m),solar rad  , Ea(hum), RhMin ,RhMax  ,pressure   ,Krs  , TDew
	et0 = asceDaily(2012.0, 10.0, 15.0, 10.7, 27.3, 1.3 , 2     , 36.82 , 98.5  , 16.502    , 1.4    , None  , None  , None      , 0.17, None);print("ET0=",et0);#every value is valid
	et0 = asceDaily(2012.0, 10.0, 15.0, 10.7, 27.3, 1.3 , 2     , 36.82 , 98.5  , None      , 1.4    , None  , None  , None      , 0.17, None);print("ET0=",et0);#solar radiation from temperatures
	et0 = asceDaily(2012.0, 10.0, 15.0, 10.7, 27.3, 1.3 , 2     , 36.82 , 98.5  , 16.502    , None   , 36.0  , 91.0  , None      , 0.17, None);print("ET0=",et0);#humidity from relative hum
	et0 = asceDaily(2012.0, 10.0, 15.0, 10.7, 27.3, 1.3 , 2     , 36.82 , 98.5  , 16.502    , None   , None  , None  , None      , 0.17, 11.7);print("ET0=",et0);#humidity from TDew
	et0 = asceDaily(2012.0, 10.0, 15.0, 10.7, 27.3, None, None  , 36.82 , 98.5  , None      , None   , None  , None  , None      , None, None);print("ET0=",et0);#everything from temp

