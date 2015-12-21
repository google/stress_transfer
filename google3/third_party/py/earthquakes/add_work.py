# Copyright (c) 2015 Google, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""Simple script that adds work to earthquake's AppEngine scheduler.

Doesn't include support
"""
from __future__ import print_function

import copy
import json
import sys
import threading
import time

# Overide Python's print function to make it output in a single blob so it works
# from multiple threads.
print = lambda x: sys.stdout.write('%s\n' % x)

import requests


# Parsing the options.
parser = OptionParser()
parser.add_option('-h', '--host', dest='host',
                  default='http://shaky-foundation-02138.appspot.com/',
                  help='AppEngine hostname that\'s running the scheduler.')

FILES = [
    's2004SUMATR01AMMO.fsp',
    's2005SUMATR01SHAO.fsp',
    's2006SOUTHE01JIxx.fsp',
    's2007BENKUL02KONC.fsp',
    's2010MAULEC01HAYE.fsp',
    's2011TOHOKU01AMMO.fsp',
    's1968HYUGAx01YAGI.fsp',
    's1968TOKACH01NAGA.fsp',
    's1969GIFUxK01TAKE.fsp',
    's1971SANFER01HEAT.fsp',
    's1974IZUxHA01TAKE.fsp',
    's1974PERUCE01HART.fsp',
    's1975OITAxK01TAKE.fsp',
    's1978MIYAGI01YAMA.fsp',
    's1978TABASI01HART.fsp',
    's1979COYOTE01LIUx.fsp',
    's1979IMPERI01ARCH.fsp',
    's1979IMPERI01HART.fsp',
    's1979IMPERI01OLSO.fsp',
    's1979IMPERI01ZENG.fsp',
    's1979PETATL01MEND.fsp',
    's1980IZUxHA01TAKE.fsp',
    's1981PLAYAA01MEND.fsp',
    's1982NEWBRU01HART.fsp',
    's1983BORAHP01MEND.fsp',
    's1983JAPANE01FUKU.fsp',
    's1984MORGAN01BERO.fsp',
    's1984MORGAN01HART.fsp',
    's1984NAGANO01TAKE.fsp',
    's1985CENTRA01MEND.fsp',
    's1985MICHOA01MEND.fsp',
    's1985NAHANN01HART.fsp',
    's1985NAHANN02HART.fsp',
    's1985ZIHUAT01MEND.fsp',
    's1986NORTHP01HART.fsp',
    's1986NORTHP01MEND.fsp',
    's1987ELMORE01LARS.fsp',
    's1987SUPERS01LARS.fsp',
    's1987SUPERS01WALD.fsp',
    's1987WHITTI01HART.fsp',
    's1988SAGUEN01HART.fsp',
    's1989LOMAPR01BERO.fsp',
    's1989LOMAPR01EMOL.fsp',
    's1989LOMAPR01STEI.fsp',
    's1989LOMAPR01WALD.fsp',
    's1989LOMAPR01ZENG.fsp',
    's1989UNGAVA01HART.fsp',
    's1991SIERRA01WALD.fsp',
    's1992JOSHUA01BENN.fsp',
    's1992JOSHUA01HOUG.fsp',
    's1992LANDER01COHE.fsp',
    's1992LANDER01COTT.fsp',
    's1992LANDER01HERN.fsp',
    's1992LANDER01WALD.fsp',
    's1992LANDER01ZENG.fsp',
    's1992LITTLE01SILV.fsp',
    's1993HOKKAI01MEND.fsp',
    's1993HOKKAI01TANI.fsp',
    's1994NORTHR01DREG.fsp',
    's1994NORTHR01HART.fsp',
    's1994NORTHR01HUDN.fsp',
    's1994NORTHR01SHEN.fsp',
    's1994NORTHR01WALD.fsp',
    's1994NORTHR01ZENG.fsp',
    's1994SANRIK01NAGA.fsp',
    's1994SANRIK01NAKA.fsp',
    's1995COLIMA01MEND.fsp',
    's1995COPALA01COUR.fsp',
    's1995KOBEJA01CHOx.fsp',
    's1995KOBEJA01HORI.fsp',
    's1995KOBEJA01IDEx.fsp',
    's1995KOBEJA01KOKE.fsp',
    's1995KOBEJA01SEKI.fsp',
    's1995KOBEJA01WALD.fsp',
    's1995KOBEJA01YOSH.fsp',
    's1995KOBEJA01ZENG.fsp',
    's1995KOBEJA02SEKI.fsp',
    's1996HYUGAx01YAGI.fsp',
    's1996HYUGAx02YAGI.fsp',
    's1996NAZCAR01SALI.fsp',
    's1996NAZCAR01SPEN.fsp',
    's1997COLFIO01HERN.fsp',
    's1997COLFIO02HERN.fsp',
    's1997COLFIO03HERN.fsp',
    's1997KAGOSH01HORI.fsp',
    's1997KAGOSH01MIYA.fsp',
    's1997KAGOSH02HORI.fsp',
    's1997YAMAGU01IDEx.fsp',
    's1997YAMAGU01MIYA.fsp',
    's1997ZIRKUH01SUDH.fsp',
    's1998ANTARC01ANTO.fsp',
    's1998ANTARC02ANTO.fsp',
    's1998HIDASW05IDEx.fsp',
    's1998HIDASW07IDEx.fsp',
    's1998HIDASW08IDEx.fsp',
    's1998HIDASW09IDEx.fsp',
    's1998HIDASW10IDEx.fsp',
    's1998HIDASW11IDEx.fsp',
    's1998HIDASW16IDEx.fsp',
    's1998IWATEJ01MIYA.fsp',
    's1998IWATEJ01NAKA.fsp',
    's1999CHICHI01CHIx.fsp',
    's1999CHICHI01JOHN.fsp',
    's1999CHICHI01MAxx.fsp',
    's1999CHICHI01SEKI.fsp',
    's1999CHICHI01WUxx.fsp',
    's1999CHICHI01ZENG.fsp',
    's1999CHICHI02MAxx.fsp',
    's1999DUZCET01BIRG.fsp',
    's1999DUZCET01DELO.fsp',
    's1999HECTOR01JIxx.fsp',
    's1999HECTOR01JONS.fsp',
    's1999HECTOR01KAVE.fsp',
    's1999HECTOR01SALI.fsp',
    's1999IZMITT01BOUC.fsp',
    's1999IZMITT01CAKI.fsp',
    's1999IZMITT01DELO.fsp',
    's1999IZMITT01REIL.fsp',
    's1999IZMITT01SEKI.fsp',
    's1999IZMITT01YAGI.fsp',
    's1999OAXACA01HERN.fsp',
    's2000KLEIFA01SUDH.fsp',
    's2000TOTTOR01IWAT.fsp',
    's2000TOTTOR01PIAT.fsp',
    's2000TOTTOR01SEKI.fsp',
    's2000TOTTOR01SEMM.fsp',
    's2001BHUJIN01ANTO.fsp',
    's2001BHUJIN01COPL.fsp',
    's2001BHUJIN01YAGI.fsp',
    's2001GEIYOJ01KAKE.fsp',
    's2001GEIYOJ01SEKI.fsp',
    's2002DENALI01ASAN.fsp',
    's2002DENALI01OGLE.fsp',
    's2003BAMIRA01POIA.fsp',
    's2003BOUMER01SEMM.fsp',
    's2003CARLSB01WEIx.fsp',
    's2003COLIMA01YAGI.fsp',
    's2003MIYAGI01HIKI.fsp',
    's2003MIYAGI01MIUR.fsp',
    's2003TOKACH01KOKE.fsp',
    's2003TOKACH01TANI.fsp',
    's2003TOKACH01YAGI.fsp',
    's2003TOKACH01YAMA.fsp',
    's2004IRIANx01WEIx.fsp',
    's2004PARKFI01CUST.fsp',
    's2004PARKFI01DREG.fsp',
    's2004PARKFI01JIxx.fsp',
    's2004SUMATR01AMMO.fsp',
    's2004SUMATR01JIxx.fsp',
    's2004SUMATR01RHIE.fsp',
    's2004SUMATR02RHIE.fsp',
    's2005FUKUOK01ASAN.fsp',
    's2005HONSHU01SHAO.fsp',
    's2005KASHMI01KONC.fsp',
    's2005KASHMI01SHAO.fsp',
    's2005NORTHE01SHAO.fsp',
    's2005SUMATR01JIxx.fsp',
    's2005SUMATR01KONC.fsp',
    's2005SUMATR01SHAO.fsp',
    's2006JAVAIN01YAGI.fsp',
    's2006KURILI01JIxx.fsp',
    's2006KURILI01LAYx.fsp',
    's2006KURILI02SLAD.fsp',
    's2006PINGTU01YENx.fsp',
    's2006PINGTU02YENx.fsp',
    's2006SOUTHE01JIxx.fsp',
    's2006SOUTHE01KONC.fsp',
    's2007BENGKU01GUSM.fsp',
    's2007BENGKU02GUSM.fsp',
    's2007BENKUL01JIxx.fsp',
    's2007BENKUL01KONC.fsp',
    's2007BENKUL02KONC.fsp',
    's2007KURILI01JIxx.fsp',
    's2007KURILI01SLAD.fsp',
    's2007NIIGAT01CIRE.fsp',
    's2007PAGAII01JIxx.fsp',
    's2007PAGAII01KONC.fsp',
    's2007PAGAII01SLAD.fsp',
    's2007PISCOP01JIxx.fsp',
    's2007PISCOP01KONC.fsp',
    's2007PISCOP01SLAD.fsp',
    's2007SOLOMO01JIxx.fsp',
    's2007TOCOPI01BEJA.fsp',
    's2007TOCOPI01JIxx.fsp',
    's2007TOCOPI01MOTA.fsp',
    's2007TOCOPI01SLAD.fsp',
    's2007TOCOPI01ZENG.fsp',
    's2007TOCOPI02BEJA.fsp',
    's2007TOCOPI03BEJA.fsp',
    's2008HONSHU01HAYE.fsp',
    's2008IWATEx01CULT.fsp',
    's2008KERMED01HAYE.fsp',
    's2008SIMEUL01HAYE.fsp',
    's2008SIMEUL01SLAD.fsp',
    's2008SULAWE01SLAD.fsp',
    's2008WENCHU01FIEL.fsp',
    's2008WENCHU01JIxx.fsp',
    's2008WENCHU01SLAD.fsp',
    's2008WENCHU01YAGI.fsp',
    's2008WENCHU02FIEL.fsp',
    's2008WENCHU03FIEL.fsp',
    's2009FIORDL01HAYE.fsp',
    's2009GULFOF01HAYE.fsp',
    's2009LAQUIL01CIRE.fsp',
    's2009LAQUIL01GUAL.fsp',
    's2009LAQUIL01POIA.fsp',
    's2009LAQUIL02CIRE.fsp',
    's2009LAQUIL02POIA.fsp',
    's2009LAQUIL03CIRE.fsp',
    's2009LAQUIL04CIRE.fsp',
    's2009LAQUIL05CIRE.fsp',
    's2009OFFSHO01HAYE.fsp',
    's2009PADANG01HAYE.fsp',
    's2009PADANG01SLAD.fsp',
    's2009PADANG02SLAD.fsp',
    's2009PAPUAx01HAYE.fsp',
    's2009SAMOAx01HAYE.fsp',
    's2009VANUAT01HAYE.fsp',
    's2009VANUAT01SLAD.fsp',
    's2010BONINI01HAYE.fsp',
    's2010DARFIE01ATZO.fsp',
    's2010DARFIE01HAYE.fsp',
    's2010ELMAYO01WEIx.fsp',
    's2010HAITIx01CALA.fsp',
    's2010HAITIx01HAYE.fsp',
    's2010HAITIx01SLAD.fsp',
    's2010HAITIx02HAYE.fsp',
    's2010MAULEC01DELO.fsp',
    's2010MAULEC01HAYE.fsp',
    's2010MAULEC01LORI.fsp',
    's2010MAULEC01LUTT.fsp',
    's2010MAULEC01SHAO.fsp',
    's2010MAULEC01SLAD.fsp',
    's2010MAULEC02LORI.fsp',
    's2010NORTHE01HAYE.fsp',
    's2010NORTHE02HAYE.fsp',
    's2010SUMATR01HAYE.fsp',
    's2010VANUAT01HAYE.fsp',
    's2011HONSHU01SHAO.fsp',
    's2011HONSHU02SHAO.fsp',
    's2011HONSHU03SHAO.fsp',
    's2011HONSHU04SHAO.fsp',
    's2011KERMAD01HAYE.fsp',
    's2011KERMAD02HAYE.fsp',
    's2011OFFSHO01HAYE.fsp',
    's2011PAKIST01HAYE.fsp',
    's2011PAKIST02HAYE.fsp',
    's2011TOHOKU01AMMO.fsp',
    's2011TOHOKU01FUJI.fsp',
    's2011TOHOKU01GUSM.fsp',
    's2011TOHOKU01HAYE.fsp',
    's2011TOHOKU01IDEx.fsp',
    's2011TOHOKU01LAYx.fsp',
    's2011TOHOKU01SATA.fsp',
    's2011TOHOKU01WEIx.fsp',
    's2011TOHOKU01YAGI.fsp',
    's2011TOHOKU01YAMA.fsp',
    's2011TOHOKU01YUEx.fsp',
    's2011TOHOKU02FUJI.fsp',
    's2011TOHOKU02GUSM.fsp',
    's2011TOHOKU02SATA.fsp',
    's2011TOHOKU02WEIx.fsp',
    's2011TOHOKU03SATA.fsp',
    's2011TOHOKU03WEIx.fsp',
    's2011VANTUR01HAYE.fsp',
    's2011VANTUR01SHAO.fsp',
    's2011VANUAT01HAYE.fsp',
    's2012BRAWLE01WEIx.fsp',
    's2012BRAWLE02WEIx.fsp',
    's2012COSTAR01HAYE.fsp',
    's2012COSTAR01YUEx.fsp',
    's2012EASTOF01HAYE.fsp',
    's2012MASSET01LAYx.fsp',
    's2012MASSET01SHAO.fsp',
    's2012MASSET01WEIx.fsp',
    's2012OAXACA01HAYE.fsp',
    's2012OAXACA01WEIx.fsp',
    's2012OFFSHO01HAYE.fsp',
    's2012SUMATR01HAYE.fsp',
    's2012SUMATR01SHAO.fsp',
    's2012SUMATR01WEIx.fsp',
    's2012SUMATR01YUEx.fsp',
    's2012SUMATR02HAYE.fsp',
    's2012SUMATR03HAYE.fsp',
]


def Post(url, p):
  """Sends work to the Appengine scheduler.

  Args:
    url: Url (as a string) of where we should post the parameters.
    p: Dictionary of parameters to post to the server.
  """
  print('Posting {}'.format(json.dumps(p)))
  r = requests.get(url, params=p)
  if r.status_code != requests.codes.ok:
    print('ERROR ' + json.dumps(p) + r.text)


def Linspace(start, end, steps):
  """Generator that mimics numpy's Linspace."""
  start, end = min(start, end), max(start, end)
  step = (end - start) / float(steps - 1)
  for i in range(int(steps) - 1):
    yield i * step + start
  yield end


def main(unused_argv):
  (options, _) = parser.parse_args()
  url = options.host + '/scheduler/add_work'

  threads = []
  for f in FILES:
    # Set your custom parameters here.
    p = {
        'srcmod': f,
        'coefficient_of_friction': 0.4,
        'mu_lambda_lame': 3e10,
        'near_field_distance': 300e3,
        'spacing_grid': 5e3,
        'days': 365,
        'isc_catalog': 'rev',
    }
    for depth in Linspace(-2.5e3, -47.5e3, 10):  # Hector
      p['obs_depth'] = depth
      # Note we copy over the parameters because thread.Threading doesn't do a
      # deep copy, instead just using parameter references.
      thread = threading.Thread(target=Post, args=(url, copy.copy(p)))
      thread.start()
      threads.append(thread)
    # Throttle back our connections. Too many to appengine makes the instance
    # unhappy.
    time.sleep(5)
  for t in threads:
    t.join()
  print('{}'.format(len(threads)))


if __name__ == '__main__':
  main(sys.argv)
