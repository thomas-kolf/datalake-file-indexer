Microsoft Windows [Version 10.0.17763.8880]
(c) 2018 Microsoft Corporation. All rights reserved.

C:\Processing>robotest.bat
================================================
ROBocopy TEST
Source:      V:\
Destination: \\vt1.vitesco.com\SMT\didv0776\DataTransfer\Keyence_VR5200_Data
Log:         C:\Processing\robocopy_test.txt
================================================


-------------------------------------------------------------------------------
   ROBOCOPY     ::     Robust File Copy for Windows
-------------------------------------------------------------------------------

  Started : Freitag, 7. August 2026 12:02:38
   Source - V:\" \vt1.vitesco.com\SMT\didv0776\DataTransfer\Keyence_VR5200_Data \S \COPY:DAT \DCOPY:T \R:2 \W:2 \XJ \XD System\
     Dest - C:\Processing\Volume\

    Files :
  Options : /DCOPY:DA /COPY:DAT /R:1000000 /W:30

------------------------------------------------------------------------------

ERROR : Invalid Parameter #3 : "Information $RECYCLE.BIN /LOG+:C:\Processing\robocopy_test.txt /TEE"

       Simple Usage :: ROBOCOPY source destination /MIR

             source :: Source Directory (drive:\path or \\server\share\path).
        destination :: Destination Dir  (drive:\path or \\server\share\path).
               /MIR :: Mirror a complete directory tree.

    For more usage information run ROBOCOPY /?


****  /MIR can DELETE files as well as copy them !

================================================
ROBOCOPY EXIT CODE: 16
================================================
Robocopy FAILED.

Check the detailed log:
C:\Processing\robocopy_test.txt

Press any key to continue . . .

C:\Processing>