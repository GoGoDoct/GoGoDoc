from gogodoc.domain.reference.admin_code import location_to_codes

def test_서울_강남구():
    sido, sggu = location_to_codes("서울 강남구")
    assert sido == "110000"
    assert sggu != ""

def test_서울만():
    sido, sggu = location_to_codes("서울")
    assert sido == "110000"
    assert sggu == ""

def test_부산():
    sido, sggu = location_to_codes("부산광역시 해운대구")
    assert sido == "210000"

def test_알수없는_지역():
    sido, sggu = location_to_codes("알수없는지역")
    assert sido == ""
    assert sggu == ""
