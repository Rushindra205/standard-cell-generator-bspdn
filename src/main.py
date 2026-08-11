import sys

from parser.cdl_parser import CDLParser


def main():

    if len(sys.argv) != 2:
        print("Usage:")
        print("python src/main.py <cell_name>")
        return


    parser = CDLParser("Benchmarks/NangateOpenCellLibrary.cdl")

    cell = parser.parse_cell(sys.argv[1])

    print(cell)



if __name__ == "__main__":
    main()