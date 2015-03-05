"""
Read/write ticDat objects from xls files. Requires the xlrd/xlrt module
"""
import utils as utls
from utils import freezableFactory, TicDatError, verify, containerish, doIt
import os
from collections import defaultdict
from itertools import product

try:
    import xlrd
    import xlwt
    importWorked=True
except:
    importWorked=False

class XlsTicFactory(freezableFactory(object, "_isFrozen")) :
    def __init__(self, ticDatFactory):
        assert importWorked, "don't create this otherwise"
        self.ticDatFactory = ticDatFactory
        self._isFrozen = True
    def createTicDat(self, xlsFilePath):
        return self.ticDatFactory.TicDat(**self._createTicDat(xlsFilePath))
    def createFrozenTicDat(self, xlsFilePath):
        return self.ticDatFactory.FrozenTicDat(**self._createTicDat(xlsFilePath))
    def _getSheetsAndFields(self, xlsFilePath, allTables):
        try :
            book = xlrd.open_workbook(xlsFilePath)
        except Exception as e:
            raise TicDatError("Unable to open %s as xls file : %s"%(xlsFilePath, e.message))
        sheets = defaultdict(list)
        for table, sheet in product(allTables, book.sheets()) :
            if table == sheet.name :
                sheets[table].append(sheet)
        missingSheets = set(allTables).difference(sheets)
        verify(not missingSheets, "The following sheet names could not be found : " + ",".join(missingSheets))
        duplicatedSheets = tuple(_t for _t,_s in sheets.items() if len(_s) > 1)
        verify(not duplicatedSheets, "The following sheet names were duplicated : " + ",".join(duplicatedSheets))
        sheets = utls.FrozenDict({k:v[0] for k,v in sheets.items() })
        fieldIndicies, badFields = {}, defaultdict(list)
        for table, sheet in sheets.items() :
            fieldIndicies[table] = self._getFieldIndicies(table, sheet, badFields[table] )
        verify(not any(_ for _ in badFields.values()), "The following field names could not be found : \n" +
               "\n".join("%s : "%t + ",".join(bf) for t,bf in badFields.items() if bf))
        return sheets, fieldIndicies
    def _createGeneratorObj(self, xlsFilePath, table):
        tdf = self.ticDatFactory
        def tableObj() :
            sheets, fieldIndicies = self._getSheetsAndFields(xlsFilePath, (table,))
            sheet = sheets[table]
            tableLen = min(len(sheet.col_values(fieldIndicies[table][field])) for field in tdf.dataFields[table])
            for x in (sheet.row_values(i) for i in range(tableLen)[1:]) :
                yield self._subTuple(tdf.dataFields[table], fieldIndicies[table])(x)
        return tableObj

    def _createTicDat(self, xlsFilePath):
        tdf = self.ticDatFactory
        rtn = {}
        sheets, fieldIndicies = self._getSheetsAndFields(xlsFilePath,
                                    set(tdf.allTables).difference(tdf.generatorTables))
        for table, sheet in sheets.items() :
            fields = tdf.primaryKeyFields.get(table, ()) + tdf.dataFields.get(table, ())
            indicies = fieldIndicies[table]
            tableLen = min(len(sheet.col_values(indicies[field])) for field in fields)
            if tdf.primaryKeyFields.get(table, ()) :
                tableObj = {self._subTuple(tdf.primaryKeyFields[table], indicies)(x) :
                            self._subTuple(tdf.dataFields.get(table, ()), indicies)(x)
                            for x in (sheet.row_values(i) for i in range(tableLen)[1:])}
            else :
                tableObj = [self._subTuple(tdf.dataFields.get(table, ()), indicies)(x)
                            for x in (sheet.row_values(i) for i in range(tableLen)[1:])]
            rtn[table] = tableObj
        for table in tdf.generatorTables :
            rtn[table] = self._createGeneratorObj(xlsFilePath, table)
        return rtn

    def _subTuple(self, fields, fieldIndicies) :
        assert set(fields).issubset(fieldIndicies)
        def rtn(x) :
            if len(fields) == 1 :
                return x[fieldIndicies[fields[0]]]
            return tuple(x[fieldIndicies[field]] for field in fields)
        return rtn

    def _getFieldIndicies(self, table, sheet, badFieldsRtn = None) :
        fields = self.ticDatFactory.primaryKeyFields.get(table, ()) + self.ticDatFactory.dataFields.get(table, ())
        if not sheet.nrows :
            doIt(badFieldsRtn.append(x) for x in fields)
            return None
        badFieldsRtn = badFieldsRtn if badFieldsRtn is not None else list()
        assert hasattr(badFieldsRtn, "append")
        tempRtn = {field:list() for field in fields}
        for field, (ind, val) in product(fields, enumerate(sheet.row_values(0))) :
            if field == val :
                tempRtn[field].append(ind)
        rtn = {field : inds[0] for field, inds in tempRtn.items() if len(inds)==1}
        doIt(badFieldsRtn.append(field) for field, inds in tempRtn.items() if len(inds)!=1)
        return rtn if len(rtn) == len(fields) else None

    def writeFile(self, ticDat, xlsFilePath, allowOverwrite = True):
        tdf = self.ticDatFactory
        msg = []
        if not self.ticDatFactory.goodTicDatObject(ticDat, lambda m : msg.append(m)) :
            raise TicDatError("Not a valid ticDat object for this schema : " + " : ".join(msg))
        verify(not os.path.isdir(xlsFilePath), "A directory is not a valid xls file path")
        verify(allowOverwrite or not os.path.exists(xlsFilePath),
               "The %s path exists and overwrite is not allowed"%xlsFilePath)
        book = xlwt.Workbook()
        for t in  sorted(sorted(tdf.allTables), key=lambda x: len(tdf.primaryKeyFields.get(x, ()))) :
            sheet = book.add_sheet(t)
            for i,f in enumerate(tdf.primaryKeyFields.get(t,()) + tdf.dataFields.get(t, ())) :
                sheet.write(0, i, f)
            _t = getattr(ticDat, t)
            if utls.dictish(_t) :
                for rowInd, (primaryKey, dataRow) in enumerate(_t.items()) :
                    for fieldInd, cellValue in enumerate( (primaryKey if containerish(primaryKey) else (primaryKey,)) +
                                        tuple(dataRow[_f] for _f in tdf.dataFields.get(t, ()))):
                        sheet.write(rowInd+1, fieldInd, cellValue)
            else :
                for rowInd, dataRow in enumerate(_t if containerish(_t) else _t()) :
                    for fieldInd, cellValue in enumerate(tuple(dataRow[_f] for _f in tdf.dataFields[t])) :
                        sheet.write(rowInd+1, fieldInd, cellValue)
        if os.path.exists(xlsFilePath):
            os.remove(xlsFilePath)
        book.save(xlsFilePath)

